
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.core.rate_limiter import limiter
from app.database import Base, enable_sqlite_foreign_keys, get_db
from app.main import app
from app.models.user import User


# Base SQLite en mémoire : aucune donnée réelle n'est modifiée.
TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

event.listen(test_engine, "connect", enable_sqlite_foreign_keys)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


@pytest.fixture()
def test_environment():
    """Prépare une base isolée et remplace la dépendance get_db."""

    limiter.reset()
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield

    limiter.reset()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def test_db(test_environment):
    """Fournit une session SQLAlchemy sur la base de test isol?e."""

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_authenticated_client(role: str) -> TestClient:
    """Crée un utilisateur de test et un client HTTP authentifié."""

    db = TestingSessionLocal()

    try:
        user = User(
            full_name=f"Test {role.capitalize()}",
            email=f"{role}@clientpulse.com",
            hashed_password=hash_password("TestPassword123!"),
            role=role,
            is_active=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token(str(user.id))

    finally:
        db.close()

    return TestClient(
        app,
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.fixture()
def client(test_environment):
    """Client authentifié avec un compte agent."""

    with create_authenticated_client("agent") as test_client:
        yield test_client


@pytest.fixture()
def admin_client(test_environment):
    """Client authentifié avec un compte administrateur."""

    with create_authenticated_client("admin") as test_client:
        yield test_client


@pytest.fixture()
def unauthenticated_client(test_environment):
    """Client HTTP sans authentification."""

    with TestClient(app) as test_client:
        yield test_client
