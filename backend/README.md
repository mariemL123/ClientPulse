# ClientPulse Backend

API REST de ClientPulse, développée avec FastAPI, SQLAlchemy et Alembic.

## Architecture

- `app/` : application FastAPI, configuration, modèles, routes et sécurité.
- `migrations/` : migrations de base de données.
- `tests/` : tests automatisés.
- `alembic.ini` : configuration Alembic.
- `requirements.txt` : dépendances Python.
- `pytest.ini` : configuration Pytest.
- `.env.example` : modèle de configuration.

## Prérequis

- Python 3.13
- pip
- PowerShell sous Windows

## Installation

Depuis la racine du dépôt ClientPulse :

    py -3.13 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt

## Configuration

Créer le fichier local `backend/.env` à partir du modèle `backend/.env.example`, sans écraser un fichier `.env` déjà configuré.

Variables disponibles :

| Variable | Description |
|---|---|
| ENVIRONMENT | Environnement : development, testing ou production |
| DEBUG | Active ou désactive le mode debug |
| DATABASE_URL | URL de connexion à la base de données |
| SECRET_KEY | Clé secrète de sécurité |
| ACCESS_TOKEN_EXPIRE_MINUTES | Durée de validité des jetons |
| CORS_ORIGINS | Origines autorisées pour le frontend |

Ne jamais versionner le fichier `.env` ni publier de clés secrètes.

## Base de données et migrations

Depuis la racine du dépôt :

    Push-Location .\backend
    try {
        ..\.venv\Scripts\python.exe -m alembic upgrade head
        ..\.venv\Scripts\python.exe -m alembic current
        ..\.venv\Scripts\python.exe -m alembic check
    }
    finally {
        Pop-Location
    }

Toute nouvelle migration doit correspondre à une modification réelle des modèles. Relire les migrations générées avant application.

## Démarrage du serveur

Depuis la racine du dépôt :

    Push-Location .\backend
    try {
        ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
    }
    finally {
        Pop-Location
    }

Adresses locales :

- API : http://127.0.0.1:8000
- Swagger : http://127.0.0.1:8000/docs
- ReDoc : http://127.0.0.1:8000/redoc
- Santé : http://127.0.0.1:8000/health

## Tests

Depuis la racine du dépôt :

    Push-Location .\backend
    try {
        ..\.venv\Scripts\python.exe -m pytest
    }
    finally {
        Pop-Location
    }

## Production

Avant le déploiement :

- Définir `ENVIRONMENT=production`.
- Définir `DEBUG=false`.
- Utiliser PostgreSQL.
- Générer une `SECRET_KEY` robuste et aléatoire.
- Configurer `CORS_ORIGINS` avec les origines HTTPS exactes du frontend.
- Configurer les variables d'environnement dans la plateforme d'hébergement.
- Appliquer les migrations sur la base de production.
- Vérifier les tests et les endpoints après déploiement.

Ne jamais exposer les secrets dans le frontend.

## Technologies

Python, FastAPI, SQLAlchemy, Alembic, Pydantic Settings, SQLite, PostgreSQL, Pytest et HTTPX.