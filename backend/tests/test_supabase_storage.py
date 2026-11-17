"""Tests unitaires du stockage Supabase, sans accès réseau réel."""

import asyncio
import io

import httpx
import pytest
from PIL import Image
from starlette.datastructures import UploadFile

from app.services import file_storage


@pytest.fixture
def supabase_config(monkeypatch, tmp_path):
    """Configure Supabase avec des identifiants fictifs."""

    monkeypatch.setattr(file_storage.settings, "STORAGE_BACKEND", "supabase")
    monkeypatch.setattr(
        file_storage.settings,
        "SUPABASE_URL",
        "https://example.supabase.co",
    )
    monkeypatch.setattr(
        file_storage.settings,
        "SUPABASE_SERVICE_ROLE_KEY",
        "test-service-role-key",
    )
    monkeypatch.setattr(
        file_storage.settings,
        "SUPABASE_AVATARS_BUCKET",
        "clientpulse-avatars",
    )
    monkeypatch.setattr(file_storage.settings, "STORAGE_DIR", tmp_path)

    return tmp_path


def make_png() -> bytes:
    """Génère une image PNG valide en mémoire."""

    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "blue").save(buffer, format="PNG")
    return buffer.getvalue()


def make_upload(content: bytes, filename: str = "avatar.png") -> UploadFile:
    """Construit un upload indépendant de l'API HTTP."""

    return UploadFile(file=io.BytesIO(content), filename=filename)


class FakeResponse:
    """Simule une réponse HTTP."""

    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request(
                "GET",
                "https://example.supabase.co",
            )
            response = httpx.Response(
                self.status_code,
                request=request,
            )
            raise httpx.HTTPStatusError(
                "Erreur HTTP simulée",
                request=request,
                response=response,
            )


class FakeAsyncClient:
    """Simule le client HTTP asynchrone de Supabase."""

    response = FakeResponse()
    captured = {}

    def __init__(self, *args, **kwargs):
        type(self).captured = {"client_kwargs": kwargs}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def post(self, url, **kwargs):
        type(self).captured["url"] = url
        type(self).captured["post_kwargs"] = kwargs
        return type(self).response


def test_supabase_object_url_builds_valid_url(supabase_config):
    """Construit une URL objet valide."""

    key = f"{'a' * 32}.png"

    result = file_storage._supabase_object_url("avatars", key)

    assert result == (
        "https://example.supabase.co/storage/v1/object/"
        f"clientpulse-avatars/{key}"
    )


@pytest.mark.parametrize(
    ("category", "key"),
    [
        ("attachments", f"{'a' * 32}.png"),
        ("avatars", "../../secret.png"),
        ("avatars", f"{'A' * 32}.png"),
        ("avatars", f"{'a' * 32}.pdf"),
        ("avatars", ""),
    ],
)
def test_supabase_object_url_rejects_invalid_values(
    supabase_config,
    category,
    key,
):
    """Refuse les catégories et clés non autorisées."""

    with pytest.raises(ValueError):
        file_storage._supabase_object_url(category, key)


def test_supabase_headers_include_credentials(supabase_config):
    """Construit les en-têtes d'authentification Supabase."""

    headers = file_storage._supabase_headers("image/png")

    assert headers["Authorization"] == "Bearer test-service-role-key"
    assert headers["apikey"] == "test-service-role-key"
    assert headers["Content-Type"] == "image/png"


def test_supabase_headers_reject_missing_key(
    supabase_config,
    monkeypatch,
):
    """Refuse une configuration sans clé de service."""

    monkeypatch.setattr(
        file_storage.settings,
        "SUPABASE_SERVICE_ROLE_KEY",
        "",
    )

    with pytest.raises(OSError):
        file_storage._supabase_headers()


def test_supabase_upload_avatar_sends_file(
    supabase_config,
    monkeypatch,
):
    """Vérifie la requête d'upload sans appel réseau."""

    FakeAsyncClient.response = FakeResponse()

    monkeypatch.setattr(
        file_storage.httpx,
        "AsyncClient",
        FakeAsyncClient,
    )

    key = f"{'b' * 32}.png"
    content = b"fake-png-content"

    asyncio.run(
        file_storage._supabase_upload_avatar(
            key,
            content,
            "image/png",
        )
    )

    captured = FakeAsyncClient.captured

    assert captured["url"].endswith(
        f"/clientpulse-avatars/{key}"
    )
    assert captured["post_kwargs"]["content"] == content
    assert captured["post_kwargs"]["headers"]["Content-Type"] == "image/png"
    assert captured["post_kwargs"]["headers"]["x-upsert"] == "false"


def test_supabase_upload_avatar_converts_http_error(
    supabase_config,
    monkeypatch,
):
    """Convertit une erreur HTTP en OSError."""

    FakeAsyncClient.response = FakeResponse(status_code=500)

    monkeypatch.setattr(
        file_storage.httpx,
        "AsyncClient",
        FakeAsyncClient,
    )

    with pytest.raises(OSError):
        asyncio.run(
            file_storage._supabase_upload_avatar(
                f"{'c' * 32}.png",
                b"content",
                "image/png",
            )
        )


def test_get_supabase_avatar_returns_content(
    supabase_config,
    monkeypatch,
):
    """Retourne les octets téléchargés."""

    expected = b"avatar-content"

    def fake_get(url, **kwargs):
        assert url.endswith(
            f"/clientpulse-avatars/{'d' * 32}.png"
        )
        assert kwargs["headers"]["apikey"] == "test-service-role-key"
        return FakeResponse(content=expected)

    monkeypatch.setattr(file_storage.httpx, "get", fake_get)

    result = file_storage.get_supabase_avatar(f"{'d' * 32}.png")

    assert result == expected


def test_get_supabase_avatar_raises_not_found(
    supabase_config,
    monkeypatch,
):
    """Transforme une réponse 404 en FileNotFoundError."""

    monkeypatch.setattr(
        file_storage.httpx,
        "get",
        lambda *args, **kwargs: FakeResponse(status_code=404),
    )

    with pytest.raises(FileNotFoundError):
        file_storage.get_supabase_avatar(f"{'e' * 32}.png")


def test_get_supabase_avatar_converts_http_error(
    supabase_config,
    monkeypatch,
):
    """Convertit une erreur réseau en OSError."""

    def fake_get(*args, **kwargs):
        request = httpx.Request(
            "GET",
            "https://example.supabase.co",
        )
        raise httpx.ConnectError("Erreur réseau simulée", request=request)

    monkeypatch.setattr(file_storage.httpx, "get", fake_get)

    with pytest.raises(OSError):
        file_storage.get_supabase_avatar(f"{'f' * 32}.png")


def test_delete_supabase_avatar_sends_request(
    supabase_config,
    monkeypatch,
):
    """Vérifie l'URL et le payload de suppression."""

    captured = {}

    def fake_delete(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setattr(file_storage.httpx, "delete", fake_delete)

    key = f"{'1' * 32}.webp"
    file_storage._delete_supabase_avatar(key)

    assert captured["url"] == (
        "https://example.supabase.co/storage/v1/object/"
        "clientpulse-avatars"
    )
    assert captured["kwargs"]["json"] == {"prefixes": [key]}
    assert (
        captured["kwargs"]["headers"]["Authorization"]
        == "Bearer test-service-role-key"
    )


def test_delete_supabase_avatar_is_idempotent_on_404(
    supabase_config,
    monkeypatch,
):
    """Accepte une suppression répétée."""

    monkeypatch.setattr(
        file_storage.httpx,
        "delete",
        lambda *args, **kwargs: FakeResponse(status_code=404),
    )

    file_storage._delete_supabase_avatar(f"{'2' * 32}.png")


def test_delete_supabase_avatar_converts_http_error(
    supabase_config,
    monkeypatch,
):
    """Convertit une erreur réseau en OSError."""

    def fake_delete(*args, **kwargs):
        request = httpx.Request(
            "DELETE",
            "https://example.supabase.co",
        )
        raise httpx.ConnectError("Erreur réseau simulée", request=request)

    monkeypatch.setattr(file_storage.httpx, "delete", fake_delete)

    with pytest.raises(OSError):
        file_storage._delete_supabase_avatar(f"{'3' * 32}.png")


def test_save_avatar_uses_supabase_and_cleans_temporary_files(
    supabase_config,
    monkeypatch,
):
    """Envoie l'avatar sur Supabase et nettoie les fichiers temporaires."""

    uploaded = {}

    async def fake_upload(storage_key, content, content_type):
        uploaded["storage_key"] = storage_key
        uploaded["content"] = content
        uploaded["content_type"] = content_type

    monkeypatch.setattr(
        file_storage,
        "_supabase_upload_avatar",
        fake_upload,
    )

    upload = make_upload(make_png())

    stored = asyncio.run(file_storage.save_avatar(upload))

    assert stored.storage_key == uploaded["storage_key"]
    assert stored.storage_key.endswith(".png")
    assert stored.content_type == "image/png"
    assert stored.size_bytes == len(uploaded["content"])
    assert uploaded["content"]
    assert upload.file.closed

    avatar_directory = supabase_config / "avatars"
    assert avatar_directory.is_dir()
    assert list(avatar_directory.iterdir()) == []


def test_delete_stored_file_uses_supabase_for_avatars(
    supabase_config,
    monkeypatch,
):
    """Délègue la suppression des avatars à Supabase."""

    captured = {}

    def fake_delete(storage_key):
        captured["storage_key"] = storage_key

    monkeypatch.setattr(
        file_storage,
        "_delete_supabase_avatar",
        fake_delete,
    )

    key = f"{'4' * 32}.jpg"

    file_storage.delete_stored_file("avatars", key)

    assert captured["storage_key"] == key
    assert not (supabase_config / "avatars" / key).exists()


def test_delete_stored_file_rejects_invalid_supabase_key(
    supabase_config,
):
    """Refuse une clé invalide avant toute suppression."""

    with pytest.raises(ValueError):
        file_storage.delete_stored_file(
            "avatars",
            "../../secret.png",
        )
