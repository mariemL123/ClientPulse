from sqlalchemy import text


def test_postgres_connection_targets_expected_database(postgres_db):
    """Vérifie la connexion effective à la base PostgreSQL de test."""

    result = postgres_db.execute(
        text("SELECT current_database(), current_user")
    ).one()

    assert result.current_database == "clientpulse_test"
    assert result.current_user == "postgres"


def test_postgres_schema_contains_expected_tables(postgres_db):
    """Vérifie la présence des tables applicatives."""

    from sqlalchemy import inspect

    tables = set(inspect(postgres_db.bind).get_table_names())

    assert {
        "clients",
        "users",
        "tickets",
        "ticket_attachments",
        "alembic_version",
    }.issubset(tables)
