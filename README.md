# ClientPulse

**A Modern Client and Ticket Management Platform**

ClientPulse is a full-stack web application designed to help businesses manage customer relationships, track support requests, and monitor operational activity through a centralized dashboard.

The project combines a React and TypeScript frontend with a Python FastAPI backend, providing a modular architecture for customer and support management.

## Key Features

- **Authentication and Authorization** — Secure user authentication with JWT tokens and role-based access.
- **Dashboard and Analytics** — Centralized overview of customer and support activity.
- **Client Management** — Create, view, update, and manage customer records.
- **Ticket Management** — Track support requests, priorities, statuses, and assignments.
- **User Management** — Manage application users, roles, and account status.
- **REST API** — Structured backend endpoints for frontend integration.
- **Database Management** — SQLAlchemy ORM and Alembic database migrations.

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React, TypeScript, Vite |
| UI and Charts | Tailwind CSS, Lucide React, Recharts |
| Backend | Python, FastAPI |
| Database | SQLite (local development), PostgreSQL (production target) |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Authentication | JWT, Argon2 password hashing |
| Testing | Pytest |
| Code Quality | ESLint, TypeScript |

## Project Architecture

```text
ClientPulse/
├── backend/
│   ├── app/
│   │   ├── models/
│   │   ├── routers/
│   │   ├── schemas/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   ├── migrations/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── assets/
│   │   ├── services/
│   │   ├── App.tsx
│   │   ├── App.css
│   │   └── index.css
│   ├── package.json
│   └── vite.config.ts
├── .gitignore
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.13+
- Node.js 22+
- npm

### 1. Clone the repository

```powershell
git clone https://github.com/mariemL123/ClientPulse.git
cd ClientPulse
```

### 2. Set up the backend

From the repository root:

```powershell
cd backend
python -m venv ..\.venv
..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` locally and configure the required values:

- `SECRET_KEY`
- `DATABASE_URL`
- `ENVIRONMENT`
- `DEBUG`
- `CORS_ORIGINS`

For local development, use a unique development secret and the local SQLite database configuration from `.env.example`. Never commit a real `.env` file or production credentials.

### 3. Run database migrations

Run this command from the `backend` directory after checking that `DATABASE_URL` points to the intended database:

```powershell
alembic upgrade head
```

Do not run migrations against an existing database without first verifying its schema and creating a backup.

### 4. Start the backend

From the `backend` directory:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Backend API: http://127.0.0.1:8000
- Interactive API documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

### 5. Set up the frontend

Open a second terminal from the repository root:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
```

The local `frontend/.env.example` configures:

```env
VITE_API_URL=http://127.0.0.1:8000
```

Start the development server:

```powershell
npm run dev
```

The frontend will be available at the local URL displayed by Vite, usually http://localhost:5173.

## Testing and Code Quality

### Backend tests

Run from the `backend` directory:

```powershell
python -m pytest -q
```

### Frontend linting and production build

Run from the `frontend` directory:

```powershell
npm run lint
npm run build
```

The optimized frontend files are generated in `frontend/dist/`.

## Security

ClientPulse incorporates several security-oriented practices:

- JWT-based authentication.
- Argon2 password hashing.
- Role-based access control.
- Environment-based configuration.
- Configurable CORS policies.
- Login rate limiting.
- Separation of application configuration and sensitive credentials.

**Production requirements:** use unique credentials, HTTPS, a strong randomly generated secret key, a PostgreSQL database, and an exact CORS allowlist containing the deployed frontend origin. Never place server secrets in frontend environment variables.

## Deployment Architecture

The selected hosting architecture is Render for all hosted components:

| Component | Render service | Configuration |
|---|---|---|
| Frontend | Static Site | Root directory: `frontend`; build: `npm ci && npm run build`; publish directory: `dist` |
| Backend | Web Service | Root directory: `backend`; build: `pip install -r requirements.txt`; start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Production database | Render PostgreSQL | Set the backend `DATABASE_URL` to the database connection string provided by Render |

### Backend environment variables

Configure these in the Render backend service settings. Do not commit their values to the repository.

- `ENVIRONMENT=production`
- `DEBUG=false`
- `SECRET_KEY` — a strong, unique, randomly generated secret.
- `DATABASE_URL` — the Render PostgreSQL connection string.
- `CORS_ORIGINS` — the exact HTTPS origin of the deployed frontend.
- `ACCESS_TOKEN_EXPIRE_MINUTES` — set according to the application's security policy.

Run the Alembic migration (`alembic upgrade head`) against the production database before the application serves production traffic. Verify the target database and take an appropriate backup before applying migrations to any database that already contains data.

### Frontend environment variable

Configure `VITE_API_URL` in the Render Static Site settings with the public HTTPS URL of the deployed backend API. Vite embeds `VITE_` variables into the client build; never put secrets in them.

Render configuration references:
- [Deploy a FastAPI app](https://render.com/docs/deploy-fastapi)
- [Render web services](https://render.com/docs/web-services)
- [Render deployment guide](https://render.com/docs/your-first-deploy)
- [Vite static deployment guide](https://vite.dev/guide/static-deploy)

**Deployment status:** the Render architecture is selected; production deployment and configuration are not yet confirmed as complete.

## Project Status

The project is under active development. The backend and frontend have been tested locally. Production deployment preparation is ongoing.

## Author

**Mariem L.**

Python Backend Developer | Full-Stack Developer | AI & Automation Enthusiast

GitHub: [mariemL123](https://github.com/mariemL123)

---

*ClientPulse — Bringing customer management and support operations together.*
