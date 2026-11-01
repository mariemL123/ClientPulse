
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.database import Base

# Importer tous les modèles pour les enregistrer dans Base.metadata.
from app.models.client import Client
from app.models.ticket import Ticket
from app.models.user import User


# Configuration Alembic.
config = context.config

# Utiliser l'URL définie dans les paramètres de l'application.
config.set_main_option(
    "sqlalchemy.url",
    settings.DATABASE_URL.replace("%", "%%"),
)

# Configurer les logs si le fichier INI le permet.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Métadonnées utilisées pour détecter les différences entre modèles et DB.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Exécute les migrations sans créer de connexion DB."""
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Exécute les migrations avec une connexion DB active."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
