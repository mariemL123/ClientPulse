"""Tests unitaires du service de stockage privé."""

import asyncio
import io
import zipfile

import pytest

from PIL import Image
from starlette.datastructures import UploadFile

from app.services import file_storage


@pytest.fixture()
def isolated_storage(tmp_path, monkeypatch):
    """Utilise un répertoire temporaire pour chaque test."""

    monkeypatch.setattr(
        file_storage.settings,
        "STORAGE_DIR",
        tmp_path,
    )
    return tmp_path


def make_upload(content: bytes, filename: str) -> UploadFile:
    """Construit un upload indépendant de l'API HTTP."""

    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
    )


def make_png() -> bytes:
    """Génère une petite image PNG valide en mémoire."""

    buffer = io.BytesIO()

    image = Image.new("RGB", (32, 32), "blue")
    image.save(buffer, format="PNG")

    return buffer.getvalue()


def test_save_avatar_valid_png(isolated_storage):
    """Un avatar PNG valide est stocké et réencodé."""

    upload = make_upload(make_png(), "avatar.png")

    stored = asyncio.run(file_storage.save_avatar(upload))

    assert stored.content_type == "image/png"
    assert stored.original_filename == "avatar.png"
    assert stored.size_bytes > 0

    path = file_storage.get_storage_path(
        "avatars",
        stored.storage_key,
    )

    assert path.is_file()

    with Image.open(path) as image:
        assert image.format == "PNG"
        assert image.size == (32, 32)


def test_save_avatar_rejects_fake_image(isolated_storage):
    """Un fichier texte renommé en PNG doit être refusé."""

    upload = make_upload(
        b"Ce fichier n'est pas une image.",
        "fake.png",
    )

    with pytest.raises(ValueError, match="Image invalide"):
        asyncio.run(file_storage.save_avatar(upload))

    assert list((isolated_storage / "avatars").glob("*")) == []


def test_save_avatar_rejects_oversized_file(isolated_storage):
    """Un avatar dépassant 2 Mo est refusé."""

    content = b"x" * (file_storage.AVATAR_MAX_SIZE + 1)
    upload = make_upload(content, "large.png")

    with pytest.raises(ValueError, match="dépasse la limite"):
        asyncio.run(file_storage.save_avatar(upload))

    assert list((isolated_storage / "avatars").glob("*")) == []


def test_save_attachment_valid_pdf(isolated_storage):
    """Un PDF portant une signature valide est accepté."""

    upload = make_upload(
        b"%PDF-1.7\nContenu de test\n",
        "document.pdf",
    )

    stored = asyncio.run(file_storage.save_attachment(upload))

    assert stored.content_type == "application/pdf"
    assert stored.original_filename == "document.pdf"

    path = file_storage.get_storage_path(
        "attachments",
        stored.storage_key,
    )

    assert path.is_file()
    assert path.read_bytes().startswith(b"%PDF-")


def test_save_attachment_rejects_fake_pdf(isolated_storage):
    """Un fichier texte renommé en PDF doit être refusé."""

    upload = make_upload(
        b"Faux document PDF",
        "fake.pdf",
    )

    with pytest.raises(ValueError, match="PDF valide"):
        asyncio.run(file_storage.save_attachment(upload))

    assert list((isolated_storage / "attachments").glob("*")) == []


def test_save_attachment_rejects_unsupported_extension(isolated_storage):
    """Les extensions non autorisées sont refusées."""

    upload = make_upload(b"contenu", "script.exe")

    with pytest.raises(ValueError, match="Extension"):
        asyncio.run(file_storage.save_attachment(upload))


def test_save_attachment_valid_txt(isolated_storage):
    """Un fichier TXT UTF-8 est accepté."""

    upload = make_upload(
        "Document de test ClientPulse.".encode("utf-8"),
        "notes.txt",
    )

    stored = asyncio.run(file_storage.save_attachment(upload))

    assert stored.content_type == "text/plain"

    path = file_storage.get_storage_path(
        "attachments",
        stored.storage_key,
    )

    assert path.read_text(encoding="utf-8") == (
        "Document de test ClientPulse."
    )


def test_save_attachment_rejects_binary_txt(isolated_storage):
    """Un fichier binaire déguisé en TXT est refusé."""

    upload = make_upload(
        b"\x00\x01\x02\x03",
        "binary.txt",
    )

    with pytest.raises(ValueError, match="données binaires"):
        asyncio.run(file_storage.save_attachment(upload))

    assert list((isolated_storage / "attachments").glob("*")) == []


def test_save_attachment_accepts_structurally_valid_docx(isolated_storage):
    """Un DOCX contenant les éléments XML requis est accepté."""

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")

    upload = make_upload(buffer.getvalue(), "document.docx")

    stored = asyncio.run(file_storage.save_attachment(upload))

    assert stored.content_type.startswith(
        "application/vnd.openxmlformats-officedocument"
    )

    assert file_storage.get_storage_path(
        "attachments",
        stored.storage_key,
    ).is_file()


def test_storage_path_rejects_path_traversal(isolated_storage):
    """Une clé contenant un chemin arbitraire est refusée."""

    with pytest.raises(ValueError, match="Clé de stockage invalide"):
        file_storage.get_storage_path(
            "attachments",
            "../../secret.txt",
        )


def test_delete_stored_file(isolated_storage):
    """Un fichier stocké peut être supprimé par sa clé."""

    upload = make_upload(
        b"%PDF-1.7\nTest\n",
        "delete-me.pdf",
    )

    stored = asyncio.run(file_storage.save_attachment(upload))

    path = file_storage.get_storage_path(
        "attachments",
        stored.storage_key,
    )

    assert path.exists()

    file_storage.delete_stored_file(
        "attachments",
        stored.storage_key,
    )

    assert not path.exists()


def test_attachment_rejects_fake_jpeg_with_valid_signature(isolated_storage):
    """Une fausse image JPEG ne doit pas être acceptée."""

    upload = make_upload(
        b"\xff\xd8\xff" + b"ceci n'est pas une image",
        "fake.jpg",
    )

    with pytest.raises(ValueError, match="Image invalide"):
        asyncio.run(file_storage.save_attachment(upload))

    assert list((isolated_storage / "attachments").glob("*")) == []


def test_attachment_rejects_extension_mismatch(isolated_storage):
    """Une image PNG ne doit pas être acceptée avec une extension JPEG."""

    upload = make_upload(make_png(), "image.jpg")

    with pytest.raises(ValueError, match="ne correspond pas"):
        asyncio.run(file_storage.save_attachment(upload))

    assert list((isolated_storage / "attachments").glob("*")) == []


def test_attachment_rejects_corrupted_docx(isolated_storage):
    """Une archive DOCX dont le CRC est incorrect doit être refusée."""

    buffer = io.BytesIO()

    with zipfile.ZipFile(
        buffer,
        "w",
        compression=zipfile.ZIP_STORED,
    ) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")

    corrupted = bytearray(buffer.getvalue())

    # Localise les données de word/document.xml dans l'archive ZIP.
    filename = b"word/document.xml"
    filename_offset = corrupted.find(filename)

    assert filename_offset >= 0

    # En-tête local ZIP : 30 octets, puis nom et données supplémentaires.
    local_header_offset = filename_offset - 30
    filename_length = int.from_bytes(
        corrupted[local_header_offset + 26:local_header_offset + 28],
        "little",
    )
    extra_length = int.from_bytes(
        corrupted[local_header_offset + 28:local_header_offset + 30],
        "little",
    )

    data_offset = (
        local_header_offset
        + 30
        + filename_length
        + extra_length
    )

    corrupted[data_offset] ^= 0x01

    upload = make_upload(bytes(corrupted), "corrupted.docx")

    with pytest.raises(ValueError, match="corrompue"):
        asyncio.run(file_storage.save_attachment(upload))

    assert list((isolated_storage / "attachments").glob("*")) == []


def test_storage_path_rejects_wrong_category_extension(isolated_storage):
    """Une clé d'avatar ne doit pas accepter une extension interdite."""

    storage_key = f"{'a' * 32}.pdf"

    with pytest.raises(ValueError, match="Clé de stockage invalide"):
        file_storage.get_storage_path("avatars", storage_key)


def test_upload_is_closed_when_storage_directory_fails(
    monkeypatch,
    isolated_storage,
):
    """L'upload doit être fermé même si le stockage est indisponible."""

    def fail_storage_directory(category):
        raise OSError("Stockage indisponible")

    monkeypatch.setattr(
        file_storage,
        "_storage_directory",
        fail_storage_directory,
    )

    upload = make_upload(make_png(), "avatar.png")

    with pytest.raises(OSError, match="Stockage indisponible"):
        asyncio.run(file_storage.save_avatar(upload))

    assert upload.file.closed
