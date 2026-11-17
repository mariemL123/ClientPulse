from getpass import getpass

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session


# Cible autorisée : base PostgreSQL locale exclusivement.
DB_HOST = "127.0.0.1"
DB_PORT = 5432
DB_NAME = "clientpulse_test"
DB_USER = "postgres"

# Dernière migration déjà appliquée et vérifiée sur cette base.
EXPECTED_REVISION = "0035261fdbc7"

REQUIRED_TABLES = {
    "alembic_version",
    "clients",
    "ticket_attachments",
    "tickets",
    "users",
}


@pytest.fixture(scope="session")
def postgres_engine():
    """Crée un moteur limité à la base PostgreSQL locale de test."""

    password = getpass(
        "Mot de passe PostgreSQL local (saisie masquée) : "
    )

    if not password:
        pytest.fail("Le mot de passe PostgreSQL ne peut pas être vide.")

    # Construction explicite de l'URL : aucune lecture de .env.
    database_url = URL.create(
        drivername="postgresql+psycopg",
        username=DB_USER,
        password=password,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    )

    # Paramètres adaptés au serveur PostgreSQL local.
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 5,
            "sslmode": "disable",
        },
    )

    try:
        # Vérifie la cible réelle avant de fournir le moteur aux tests.
        with engine.connect() as connection:
            identity = connection.execute(
                text(
                    """
                    SELECT
                        current_database(),
                        current_user,
                        inet_server_addr()::text,
                        inet_server_port()
                    """
                )
            ).one()

            database_name, database_user, server_address, server_port = identity

            if database_name != DB_NAME:
                pytest.fail("Base inattendue : accès aux tests refusé.")

            if database_user != DB_USER:
                pytest.fail("Utilisateur PostgreSQL inattendu.")

            import ipaddress

            # PostgreSQL peut retourner une adresse avec un préfixe CIDR.
            try:
                actual_ip = ipaddress.ip_interface(server_address).ip
                expected_ip = ipaddress.ip_address(DB_HOST)
            except ValueError:
                pytest.fail("Adresse IP du serveur PostgreSQL invalide.")

            if actual_ip != expected_ip or server_port != DB_PORT:
                pytest.fail("Serveur PostgreSQL inattendu.")

            # Vérifie que les migrations attendues sont déjà présentes.
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()

            if revision != EXPECTED_REVISION:
                pytest.fail(
                    "Révision Alembic inattendue. "
                    "Aucune migration automatique ne sera exécutée."
                )

            # Vérifie les tables sans modifier le schéma.
            existing_tables = set(inspect(connection).get_table_names())
            missing_tables = REQUIRED_TABLES - existing_tables

            if missing_tables:
                pytest.fail(
                    f"Tables PostgreSQL manquantes : {sorted(missing_tables)}"
                )

        yield engine

    finally:
        engine.dispose()


@pytest.fixture()
def postgres_db(postgres_engine):
    """
    Fournit une session isolée par transaction.

    Même si un test appelle commit(), la transaction externe
    est annulée à la fin du test.
    """

    connection = postgres_engine.connect()
    transaction = connection.begin()

    session = Session(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        session.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()
