
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


# Configuration du moteur SQLAlchemy.
# SQLite nécessite une option spécifique pour FastAPI.
connect_args = {}

if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False


engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)


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
