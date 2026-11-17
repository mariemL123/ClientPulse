
"""Stockage privé et validation des fichiers téléversés."""

from __future__ import annotations

import asyncio

import httpx
import os
import re
import uuid
import warnings
import zipfile
import zlib

from dataclasses import dataclass
from pathlib import Path, PurePath
from urllib.parse import quote

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import settings


AVATAR_MAX_SIZE = 2 * 1024 * 1024
ATTACHMENT_MAX_SIZE = 10 * 1024 * 1024

CHUNK_SIZE = 64 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_ZIP_ENTRIES = 2_000
MAX_ZIP_UNCOMPRESSED_SIZE = 50 * 1024 * 1024
MAX_ZIP_COMPRESSION_RATIO = 1_000

AVATAR_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}

ATTACHMENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
    ".xlsx": (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
    ".txt": "text/plain",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

AVATAR_EXTENSIONS = {".jpg", ".png", ".webp"}

_INVALID_FILENAME_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_STORAGE_KEY_PATTERN = re.compile(
    r"(?P<identifier>[a-f0-9]{32})(?P<extension>\.[a-z0-9]{2,5})"
)




# Timeout r?seau born? pour ?viter de bloquer ind?finiment les requ?tes.
_SUPABASE_TIMEOUT = httpx.Timeout(20.0, connect=5.0)


def _supabase_object_url(category: str, storage_key: str) -> str:
    """Construit une URL Storage apr?s validation stricte de la cl?."""

    if category != "avatars":
        raise ValueError("Cat?gorie Supabase non prise en charge.")

    if (
        not isinstance(storage_key, str)
        or re.fullmatch(r"[0-9a-f]{32}\.(?:jpg|png|webp)", storage_key) is None
    ):
        raise ValueError("Cl? de stockage invalide.")

    bucket = settings.SUPABASE_AVATARS_BUCKET
    if not bucket:
        raise OSError("Configuration du stockage Supabase incompl?te.")

    return (
        f"{settings.SUPABASE_URL}/storage/v1/object/"
        f"{quote(bucket, safe='')}/{quote(storage_key, safe='')}"
    )


def _supabase_headers(content_type: str | None = None) -> dict[str, str]:
    """Construit les en-t?tes priv?s Supabase sans exposer la cl?."""

    key = settings.SUPABASE_SERVICE_ROLE_KEY
    if not settings.SUPABASE_URL or not key:
        raise OSError("Configuration du stockage Supabase incompl?te.")

    headers = {
        "Authorization": f"Bearer {key}",
        "apikey": key,
    }

    if content_type:
        headers["Content-Type"] = content_type

    return headers


async def _supabase_upload_avatar(
    storage_key: str,
    content: bytes,
    content_type: str,
) -> None:
    """T?l?verse un avatar nettoy? dans le bucket priv?."""

    url = _supabase_object_url("avatars", storage_key)
    headers = _supabase_headers(content_type)
    headers["x-upsert"] = "false"

    try:
        async with httpx.AsyncClient(timeout=_SUPABASE_TIMEOUT) as client:
            response = await client.post(
                url,
                headers=headers,
                content=content,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise OSError(
            "Le t?l?versement vers le stockage Supabase a ?chou?."
        ) from exc


def get_supabase_avatar(storage_key: str) -> bytes:
    """T?l?charge un avatar depuis le bucket priv?."""

    url = _supabase_object_url("avatars", storage_key)

    try:
        response = httpx.get(
            url,
            headers=_supabase_headers(),
            timeout=_SUPABASE_TIMEOUT,
        )

        if response.status_code == 404:
            raise FileNotFoundError("Avatar distant introuvable.")

        response.raise_for_status()
        return response.content

    except FileNotFoundError:
        raise
    except httpx.HTTPError as exc:
        raise OSError(
            "La lecture depuis le stockage Supabase a ?chou?."
        ) from exc


def _delete_supabase_avatar(storage_key: str) -> None:
    """Supprime un avatar du bucket priv? de mani?re idempotente."""

    # R?utilise la validation stricte avant toute requ?te distante.
    _supabase_object_url("avatars", storage_key)

    url = (
        f"{settings.SUPABASE_URL}/storage/v1/object/"
        f"{quote(settings.SUPABASE_AVATARS_BUCKET, safe='')}"
    )
    payload = {"prefixes": [storage_key]}

    try:
        response = httpx.delete(
            url,
            headers=_supabase_headers(),
            json=payload,
            timeout=_SUPABASE_TIMEOUT,
        )

        # Une suppression r?p?t?e ne constitue pas une erreur.
        if response.status_code == 404:
            return

        response.raise_for_status()

    except httpx.HTTPError as exc:
        raise OSError(
            "La suppression dans le stockage Supabase a ?chou?."
        ) from exc


@dataclass(frozen=True)
class StoredFile:
    """Informations sûres retournées après un téléversement."""

    storage_key: str
    original_filename: str
    content_type: str
    size_bytes: int


def _storage_directory(category: str) -> Path:
    """Retourne un sous-dossier autorisé du stockage privé."""

    if category not in {"avatars", "attachments"}:
        raise ValueError("Catégorie de stockage invalide.")

    root = Path(settings.STORAGE_DIR).resolve()
    directory = (root / category).resolve()

    if directory.parent != root:
        raise ValueError("Chemin de stockage invalide.")

    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _safe_filename(filename: str | None) -> str:
    """Nettoie un nom de fichier sans jamais l'utiliser comme chemin."""

    raw_name = filename or "fichier"
    name = PurePath(raw_name.replace("\\", "/")).name
    name = _INVALID_FILENAME_CHARS.sub("", name).strip()
    name = name.strip(" .")

    if not name:
        name = "fichier"

    return name[:255]


async def _write_upload(
    upload: UploadFile,
    destination: Path,
    max_size: int,
) -> int:
    """Écrit un upload par blocs avec une limite stricte de taille.

    La fermeture de l'upload est assurée par save_avatar() ou
    save_attachment(), y compris si une erreur survient avant cet appel.
    """

    total_size = 0

    try:
        with destination.open("xb") as output:
            while True:
                chunk = await upload.read(CHUNK_SIZE)

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > max_size:
                    raise ValueError(
                        f"Le fichier dépasse la limite de "
                        f"{max_size // (1024 * 1024)} Mo."
                    )

                output.write(chunk)

        if total_size == 0:
            raise ValueError("Le fichier est vide.")

        return total_size

    except Exception:
        destination.unlink(missing_ok=True)
        raise


def _validate_image(source: Path) -> tuple[str, str]:
    """Vérifie le format réel et les dimensions de l'image."""

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(source) as image:
                image_format = image.format

                if image_format not in AVATAR_FORMATS:
                    raise ValueError("Format d'image non autorisé.")

                if image.width <= 0 or image.height <= 0:
                    raise ValueError("Dimensions d'image invalides.")

                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError(
                        "Les dimensions de l'image sont trop importantes."
                    )

                image.verify()

        return AVATAR_FORMATS[image_format]

    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValueError("Image invalide ou dangereuse.") from exc


def _sanitize_image(
    source: Path,
    destination: Path,
    image_format: str,
) -> None:
    """Réencode l'image pour supprimer les métadonnées non nécessaires."""

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(source) as image:
                image.load()

                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError(
                        "Les dimensions de l'image sont trop importantes."
                    )

                if image_format == "JPEG":
                    sanitized = image.convert("RGB")
                    sanitized.save(
                        destination,
                        format="JPEG",
                        quality=90,
                        optimize=True,
                    )

                elif image_format == "PNG":
                    sanitized = (
                        image.copy()
                        if image.mode in {"RGB", "RGBA"}
                        else image.convert("RGBA")
                    )
                    sanitized.save(
                        destination,
                        format="PNG",
                        optimize=True,
                    )

                elif image_format == "WEBP":
                    sanitized = (
                        image.copy()
                        if image.mode in {"RGB", "RGBA"}
                        else image.convert("RGBA")
                    )
                    sanitized.save(
                        destination,
                        format="WEBP",
                        quality=90,
                        method=4,
                    )

                else:
                    raise ValueError("Format d'image non autorisé.")

    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValueError("Impossible de traiter cette image.") from exc


def _validate_attachment_image(
    source: Path,
    extension: str,
) -> None:
    """Vérifie qu'une image jointe correspond à son extension."""

    actual_extension, _ = _validate_image(source)

    # JPEG est accepté sous les extensions .jpg et .jpeg.
    if actual_extension == ".jpg":
        valid_extensions = {".jpg", ".jpeg"}
    else:
        valid_extensions = {actual_extension}

    if extension not in valid_extensions:
        raise ValueError(
            "Le format réel de l'image ne correspond pas à son extension."
        )


def _validate_zip_document(source: Path, extension: str) -> None:
    """Vérifie la structure et l'intégrité d'une archive DOCX/XLSX."""

    required_entries = {
        ".docx": {"[Content_Types].xml", "word/document.xml"},
        ".xlsx": {"[Content_Types].xml", "xl/workbook.xml"},
    }

    if extension not in required_entries:
        raise ValueError("Extension d'archive Office invalide.")

    try:
        with zipfile.ZipFile(source, "r") as archive:
            entries = archive.infolist()

            if len(entries) > MAX_ZIP_ENTRIES:
                raise ValueError("Archive contenant trop de fichiers.")

            total_uncompressed = sum(
                entry.file_size for entry in entries
            )

            if total_uncompressed > MAX_ZIP_UNCOMPRESSED_SIZE:
                raise ValueError("Archive décompressée trop volumineuse.")

            if any(
                entry.file_size > MAX_ZIP_UNCOMPRESSED_SIZE
                for entry in entries
            ):
                raise ValueError("Une entrée de l'archive est trop volumineuse.")

            if any(entry.flag_bits & 0x1 for entry in entries):
                raise ValueError(
                    "Les archives chiffrées ne sont pas acceptées."
                )

            for entry in entries:
                if entry.file_size > 0 and entry.compress_size == 0:
                    raise ValueError("Archive avec compression invalide.")

                if entry.compress_size > 0:
                    ratio = entry.file_size / entry.compress_size

                    if ratio > MAX_ZIP_COMPRESSION_RATIO:
                        raise ValueError(
                            "Taux de compression de l'archive excessif."
                        )

            names = {entry.filename for entry in entries}

            if not required_entries[extension].issubset(names):
                raise ValueError(
                    "Le document Office ne possède pas une structure valide."
                )

            # Vérifie le CRC de chaque entrée sans extraire l'archive.
            corrupted_entry = archive.testzip()

            if corrupted_entry is not None:
                raise ValueError("Archive Office corrompue.")

    except (
        zipfile.BadZipFile,
        RuntimeError,
        EOFError,
        OSError,
        zlib.error,
    ) as exc:
        raise ValueError("Archive Office invalide ou corrompue.") from exc


def _validate_attachment(source: Path, extension: str) -> str:
    """Contrôle le contenu réel du document téléversé."""

    expected_type = ATTACHMENT_TYPES.get(extension)

    if expected_type is None:
        raise ValueError("Extension de fichier non autorisée.")

    if extension == ".pdf":
        with source.open("rb") as file:
            header = file.read(16)

        if not header.startswith(b"%PDF-"):
            raise ValueError("Le contenu n'est pas un PDF valide.")

    elif extension in {".jpg", ".jpeg", ".png"}:
        _validate_attachment_image(source, extension)

    elif extension in {".docx", ".xlsx"}:
        _validate_zip_document(source, extension)

    elif extension == ".txt":
        try:
            content = source.read_bytes()

            if b"\x00" in content:
                raise ValueError(
                    "Le fichier TXT contient des données binaires."
                )

            content.decode("utf-8-sig", errors="strict")

        except UnicodeDecodeError as exc:
            raise ValueError(
                "Le fichier TXT doit être encodé en UTF-8."
            ) from exc

    return expected_type


async def save_avatar(upload: UploadFile) -> StoredFile:
    """Valide, nettoie et stocke un avatar en local ou sur Supabase."""

    directory: Path | None = None
    temporary_source: Path | None = None
    temporary_output: Path | None = None
    final_path: Path | None = None
    storage_key: str | None = None
    remote_uploaded = False

    try:
        # Les fichiers temporaires restent locaux afin de conserver
        # le m?me pipeline de validation et de nettoyage d'image.
        directory = _storage_directory("avatars")

        temporary_source = directory / f".{uuid.uuid4().hex}.upload"
        temporary_output = directory / f".{uuid.uuid4().hex}.tmp"

        await _write_upload(
            upload,
            temporary_source,
            AVATAR_MAX_SIZE,
        )

        extension, content_type = await asyncio.to_thread(
            _validate_image,
            temporary_source,
        )

        image_format = {
            ".jpg": "JPEG",
            ".png": "PNG",
            ".webp": "WEBP",
        }[extension]

        await asyncio.to_thread(
            _sanitize_image,
            temporary_source,
            temporary_output,
            image_format,
        )

        storage_key = f"{uuid.uuid4().hex}{extension}"

        if settings.STORAGE_BACKEND == "supabase":
            # L'image a d?j? ?t? valid?e et r?encod?e.
            # Sa taille est limit?e par AVATAR_MAX_SIZE.
            content = await asyncio.to_thread(
                temporary_output.read_bytes
            )

            await _supabase_upload_avatar(
                storage_key,
                content,
                content_type,
            )
            remote_uploaded = True
            size_bytes = len(content)

        else:
            # Comportement local historique, inchang?.
            final_path = directory / storage_key
            os.replace(temporary_output, final_path)
            size_bytes = final_path.stat().st_size

        return StoredFile(
            storage_key=storage_key,
            original_filename=_safe_filename(upload.filename),
            content_type=content_type,
            size_bytes=size_bytes,
        )

    except Exception:
        # En cas d'?chec apr?s un upload distant r?ussi,
        # tente de supprimer l'objet pour ?viter un orphelin.
        if remote_uploaded and storage_key is not None:
            try:
                _delete_supabase_avatar(storage_key)
            except OSError:
                warnings.warn(
                    "Impossible de nettoyer un avatar Supabase "
                    "apr?s un ?chec de traitement.",
                    RuntimeWarning,
                    stacklevel=2,
                )

        # En mode local, supprime le fichier final ?ventuellement cr??.
        if final_path is not None:
            final_path.unlink(missing_ok=True)

        raise

    finally:
        if temporary_source is not None:
            temporary_source.unlink(missing_ok=True)

        if temporary_output is not None:
            temporary_output.unlink(missing_ok=True)

        await upload.close()


async def save_attachment(upload: UploadFile) -> StoredFile:
    """Valide et stocke une pièce jointe."""

    directory: Path | None = None
    temporary_source: Path | None = None
    storage_key: str | None = None

    try:
        original_filename = _safe_filename(upload.filename)
        extension = Path(original_filename).suffix.lower()

        if extension not in ATTACHMENT_TYPES:
            raise ValueError("Extension de fichier non autorisée.")

        directory = _storage_directory("attachments")
        temporary_source = directory / f".{uuid.uuid4().hex}.upload"

        size_bytes = await _write_upload(
            upload,
            temporary_source,
            ATTACHMENT_MAX_SIZE,
        )

        content_type = await asyncio.to_thread(
            _validate_attachment,
            temporary_source,
            extension,
        )

        storage_key = f"{uuid.uuid4().hex}{extension}"
        final_path = directory / storage_key

        os.replace(temporary_source, final_path)

        return StoredFile(
            storage_key=storage_key,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=size_bytes,
        )

    except Exception:
        if directory is not None and storage_key is not None:
            (directory / storage_key).unlink(missing_ok=True)
        raise

    finally:
        if temporary_source is not None:
            temporary_source.unlink(missing_ok=True)

        await upload.close()


def get_storage_path(category: str, storage_key: str) -> Path:
    """Résout une clé de stockage sans autoriser la traversée de chemin."""

    if not isinstance(storage_key, str):
        raise ValueError("Clé de stockage invalide.")

    match = _STORAGE_KEY_PATTERN.fullmatch(storage_key)

    if match is None:
        raise ValueError("Clé de stockage invalide.")

    extension = match.group("extension")

    if category == "avatars":
        allowed_extensions = AVATAR_EXTENSIONS
    elif category == "attachments":
        allowed_extensions = set(ATTACHMENT_TYPES)
    else:
        raise ValueError("Catégorie de stockage invalide.")

    if extension not in allowed_extensions:
        raise ValueError("Clé de stockage invalide.")

    directory = _storage_directory(category)
    path = (directory / storage_key).resolve()

    if path.parent != directory:
        raise ValueError("Chemin de stockage invalide.")

    return path


def delete_stored_file(category: str, storage_key: str) -> None:
    """Supprime un fichier local ou un avatar Supabase."""

    # Seuls les avatars sont stock?s sur Supabase.
    # La cl? est valid?e avant toute requ?te distante.
    if category == "avatars" and settings.STORAGE_BACKEND == "supabase":
        _supabase_object_url("avatars", storage_key)
        _delete_supabase_avatar(storage_key)
        return

    # Les avatars en mode local et toutes les pi?ces jointes
    # conservent le comportement de stockage local.
    path = get_storage_path(category, storage_key)
    path.unlink(missing_ok=True)
