from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models.client import Client
from app.models.ticket import Ticket
from app.models.ticket_attachment import TicketAttachment
from app.models.user import User


def unique_email(prefix: str) -> str:
    """Génère une adresse e-mail unique pour chaque test."""
    return f"{prefix}-{uuid4().hex}@example.test"


def create_client(db):
    """Crée un client de test et retourne son instance persistée."""
    client = Client(
        name="Client PostgreSQL",
        email=unique_email("client"),
    )
    db.add(client)
    db.flush()
    return client


def create_user(db):
    """Crée un utilisateur de test avec un hash fictif non réutilisable."""
    user = User(
        full_name="Agent PostgreSQL",
        email=unique_email("agent"),
        hashed_password="test-only-not-a-real-password-hash",
    )
    db.add(user)
    db.flush()
    return user


def create_ticket(db, client_id):
    """Crée un ticket rattaché à un client existant."""
    ticket = Ticket(
        title="Ticket de test PostgreSQL",
        description="Description utilisée pour les tests d'intégration.",
        client_id=client_id,
    )
    db.add(ticket)
    db.flush()
    return ticket


def create_attachment(db, ticket_id, uploaded_by_id=None):
    """Crée une pièce jointe avec des métadonnées valides."""
    attachment = TicketAttachment(
        ticket_id=ticket_id,
        uploaded_by_id=uploaded_by_id,
        original_filename="document-test.pdf",
        storage_key=f"tests/{uuid4().hex}.pdf",
        content_type="application/pdf",
        size_bytes=1024,
    )
    db.add(attachment)
    db.flush()
    return attachment


def test_user_insert_and_default_values(postgres_db):
    """Vérifie l'insertion d'un utilisateur et ses valeurs par défaut."""
    user = create_user(postgres_db)

    assert user.id is not None
    assert user.role == "agent"
    assert user.is_active is True
    assert user.must_change_password is False
    assert user.token_version == 0
    assert user.created_at is not None
    assert user.avatar_url is None


def test_client_email_must_be_unique(postgres_db):
    """Vérifie la contrainte UNIQUE sur l'e-mail des clients."""
    email = unique_email("duplicate-client")

    first = Client(name="Premier client", email=email)
    postgres_db.add(first)
    postgres_db.flush()

    second = Client(name="Second client", email=email)
    postgres_db.add(second)

    with pytest.raises(IntegrityError):
        postgres_db.flush()

    postgres_db.rollback()


def test_ticket_requires_an_existing_client(postgres_db):
    """Vérifie la contrainte de clé étrangère du ticket."""
    with pytest.raises(IntegrityError):
        postgres_db.execute(
            text(
                """
                INSERT INTO tickets (
                    title,
                    description,
                    client_id
                )
                VALUES (
                    'Ticket invalide',
                    'Client inexistant',
                    -999999
                )
                """
            )
        )

    postgres_db.rollback()


def test_client_cannot_be_deleted_while_tickets_exist(postgres_db):
    """Vérifie ON DELETE RESTRICT sur tickets.client_id."""
    client = create_client(postgres_db)
    create_ticket(postgres_db, client.id)

    with pytest.raises(IntegrityError):
        postgres_db.execute(
            text("DELETE FROM clients WHERE id = :client_id"),
            {"client_id": client.id},
        )

    postgres_db.rollback()


def test_ticket_deletion_cascades_to_attachments(postgres_db):
    """Vérifie ON DELETE CASCADE sur ticket_attachments.ticket_id."""
    client = create_client(postgres_db)
    ticket = create_ticket(postgres_db, client.id)
    attachment = create_attachment(postgres_db, ticket.id)

    attachment_id = attachment.id

    postgres_db.execute(
        text("DELETE FROM tickets WHERE id = :ticket_id"),
        {"ticket_id": ticket.id},
    )

    remaining = postgres_db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM ticket_attachments
            WHERE id = :attachment_id
            """
        ),
        {"attachment_id": attachment_id},
    ).scalar_one()

    assert remaining == 0


def test_user_deletion_sets_attachment_uploader_to_null(postgres_db):
    """Vérifie ON DELETE SET NULL sur uploaded_by_id."""
    user = create_user(postgres_db)
    client = create_client(postgres_db)
    ticket = create_ticket(postgres_db, client.id)
    attachment = create_attachment(postgres_db, ticket.id, user.id)

    attachment_id = attachment.id

    postgres_db.execute(
        text("DELETE FROM users WHERE id = :user_id"),
        {"user_id": user.id},
    )

    uploader_id = postgres_db.execute(
        text(
            """
            SELECT uploaded_by_id
            FROM ticket_attachments
            WHERE id = :attachment_id
            """
        ),
        {"attachment_id": attachment_id},
    ).scalar_one()

    assert uploader_id is None


def test_database_rejects_invalid_user_role(postgres_db):
    """Vérifie directement la contrainte CHECK du rôle PostgreSQL."""
    with pytest.raises(IntegrityError):
        postgres_db.execute(
            text(
                """
                INSERT INTO users (
                    full_name,
                    email,
                    hashed_password,
                    role,
                    created_at
                )
                VALUES (
                    'Utilisateur invalide',
                    :email,
                    'test-only-hash',
                    'superuser',
                    NOW()
                )
                """
            ),
            {"email": unique_email("invalid-role")},
        )

    postgres_db.rollback()


def test_database_rejects_non_positive_attachment_size(postgres_db):
    """Vérifie directement CHECK (size_bytes > 0)."""
    client = create_client(postgres_db)
    ticket = create_ticket(postgres_db, client.id)

    with pytest.raises(IntegrityError):
        postgres_db.execute(
            text(
                """
                INSERT INTO ticket_attachments (
                    ticket_id,
                    original_filename,
                    storage_key,
                    content_type,
                    size_bytes,
                    created_at
                )
                VALUES (
                    :ticket_id,
                    'invalid.pdf',
                    :storage_key,
                    'application/pdf',
                    0,
                    NOW()
                )
                """
            ),
            {
                "ticket_id": ticket.id,
                "storage_key": f"tests/{uuid4().hex}.pdf",
            },
        )

    postgres_db.rollback()