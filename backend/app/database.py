
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """Active les cles etrangeres SQLite."""

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()



# Utilise la même URL normalisée que celle qui sera utilisée par Alembic.
database_url = settings.database_url
parsed_url = make_url(database_url)

# SQLite nécessite une option spécifique avec FastAPI.
connect_args = {}

if parsed_url.get_backend_name() == "sqlite":
    connect_args["check_same_thread"] = False

# Création du moteur SQLAlchemy.
engine = create_engine(
    database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

if parsed_url.get_backend_name() == "sqlite":
    event.listen(engine, "connect", enable_sqlite_foreign_keys)

# Fabrique de sessions SQLAlchemy.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Classe de base des modèles SQLAlchemy.
Base = declarative_base()


def get_db():
    """Fournit une session DB et garantit sa fermeture."""

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
