"""Tests d'intégration des routes de gestion des avatars."""

import io

import pytest
from PIL import Image

from app.services import file_storage


@pytest.fixture()
def isolated_avatar_storage(tmp_path, monkeypatch):
    """Isole le stockage des avatars dans un répertoire temporaire."""

    monkeypatch.setattr(
        file_storage.settings,
        "STORAGE_DIR",
        tmp_path,
    )
    return tmp_path


def make_png(color: str = "blue") -> bytes:
    """Génère une image PNG valide en mémoire pour les tests."""

    buffer = io.BytesIO()

    image = Image.new("RGB", (32, 32), color)
    image.save(buffer, format="PNG")

    return buffer.getvalue()


def stored_avatars(storage_dir):
    """Retourne les fichiers d'avatars réellement stockés."""

    avatar_dir = storage_dir / "avatars"

    if not avatar_dir.exists():
        return []

    return list(avatar_dir.iterdir())


def test_upload_avatar_returns_public_url_without_storage_path(
    client,
    isolated_avatar_storage,
):
    """Un utilisateur peut enregistrer son avatar sans exposer son chemin."""

    response = client.put(
        "/api/auth/me/avatar",
        files={
            "file": (
                "avatar.png",
                make_png(),
                "image/png",
            )
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["avatar_url"] == (
        f"/api/auth/users/{payload['id']}/avatar"
    )
    assert "avatar_path" not in payload
    assert len(stored_avatars(isolated_avatar_storage)) == 1


def test_authenticated_user_can_retrieve_avatar(
    client,
    isolated_avatar_storage,
):
    """Un utilisateur authentifié peut consulter un avatar enregistré."""

    upload_response = client.put(
        "/api/auth/me/avatar",
        files={
            "file": (
                "avatar.png",
                make_png(),
                "image/png",
            )
        },
    )

    assert upload_response.status_code == 200

    avatar_url = upload_response.json()["avatar_url"]

    response = client.get(avatar_url)

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "private, max-age=300"

    # Vérifie que le contenu retourné est une véritable image PNG.
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.format == "PNG"
        assert image.size == (32, 32)


def test_upload_avatar_rejects_invalid_image(
    client,
    isolated_avatar_storage,
):
    """Un fichier qui n'est pas une image est refusé."""

    response = client.put(
        "/api/auth/me/avatar",
        files={
            "file": (
                "fake.png",
                b"This is not a valid image.",
                "image/png",
            )
        },
    )

    assert response.status_code == 400
    assert len(stored_avatars(isolated_avatar_storage)) == 0


def test_upload_avatar_rejects_oversized_image(
    client,
    isolated_avatar_storage,
):
    """Un avatar dépassant la limite de taille est refusé."""

    oversized_content = b"x" * (
        file_storage.AVATAR_MAX_SIZE + 1
    )

    response = client.put(
        "/api/auth/me/avatar",
        files={
            "file": (
                "large.png",
                oversized_content,
                "image/png",
            )
        },
    )

    assert response.status_code == 400
    assert len(stored_avatars(isolated_avatar_storage)) == 0


def test_upload_avatar_replaces_old_file(
    client,
    isolated_avatar_storage,
):
    """Le remplacement supprime l'ancien fichier après enregistrement."""

    first_response = client.put(
        "/api/auth/me/avatar",
        files={
            "file": (
                "first.png",
                make_png("blue"),
                "image/png",
            )
        },
    )

    assert first_response.status_code == 200

    old_files = stored_avatars(isolated_avatar_storage)

    assert len(old_files) == 1
    old_file = old_files[0]

    second_response = client.put(
        "/api/auth/me/avatar",
        files={
            "file": (
                "second.png",
                make_png("red"),
                "image/png",
            )
        },
    )

    assert second_response.status_code == 200

    new_files = stored_avatars(isolated_avatar_storage)

    assert len(new_files) == 1
    assert new_files[0] != old_file
    assert not old_file.exists()

    # L'URL publique reste liée au même utilisateur.
    assert (
        second_response.json()["avatar_url"]
        == first_response.json()["avatar_url"]
    )


def test_delete_avatar_removes_file_and_is_idempotent(
    client,
    isolated_avatar_storage,
):
    """La suppression retire le fichier et peut être répétée."""

    upload_response = client.put(
        "/api/auth/me/avatar",
        files={
            "file": (
                "avatar.png",
                make_png(),
                "image/png",
            )
        },
    )

    assert upload_response.status_code == 200
    assert len(stored_avatars(isolated_avatar_storage)) == 1

    avatar_url = upload_response.json()["avatar_url"]

    delete_response = client.delete("/api/auth/me/avatar")

    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert len(stored_avatars(isolated_avatar_storage)) == 0

    # Après suppression, l'avatar n'est plus accessible.
    get_response = client.get(avatar_url)

    assert get_response.status_code == 404

    # Supprimer un avatar déjà absent doit rester sans erreur.
    second_delete_response = client.delete("/api/auth/me/avatar")

    assert second_delete_response.status_code == 204


def test_get_avatar_without_existing_avatar_returns_404(client):
    """Un utilisateur sans avatar reçoit une réponse 404."""

    profile_response = client.get("/api/auth/me")

    assert profile_response.status_code == 200

    user_id = profile_response.json()["id"]

    response = client.get(
        f"/api/auth/users/{user_id}/avatar"
    )

    assert response.status_code == 404


def test_avatar_routes_require_authentication(
    client,
    unauthenticated_client,
    isolated_avatar_storage,
):
    """Les routes d'avatar refusent les requêtes non authentifiées."""

    profile_response = client.get("/api/auth/me")

    assert profile_response.status_code == 200

    user_id = profile_response.json()["id"]
    avatar_url = f"/api/auth/users/{user_id}/avatar"

    upload_response = unauthenticated_client.put(
        "/api/auth/me/avatar",
        files={
            "file": (
                "avatar.png",
                make_png(),
                "image/png",
            )
        },
    )

    delete_response = unauthenticated_client.delete(
        "/api/auth/me/avatar"
    )

    get_response = unauthenticated_client.get(avatar_url)

    assert upload_response.status_code == 401
    assert delete_response.status_code == 401
    assert get_response.status_code == 401

    # Aucun fichier ne doit être créé sans authentification.
    assert len(stored_avatars(isolated_avatar_storage)) == 0