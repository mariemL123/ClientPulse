from fastapi import FastAPI
from app.routers.users import router as users_router
from app.routers.dashboard import router as dashboard_router
from app.routers.auth import router as auth_router
from app.routers.client import router as clients_router
from app.routers.ticket import router as tickets_router


app = FastAPI(
    title="ClientPulse API",
    description="API de gestion des clients et des réclamations.",
    version="0.2.0",
)

# Enregistrement des tables SQLAlchemy dans SQLite.


# Enregistrement des routes REST.
app.include_router(clients_router)
app.include_router(tickets_router)
app.include_router(dashboard_router)
app.include_router(auth_router)
app.include_router(users_router)

@app.get("/")
def root():
    return {
        "message": "Bienvenue sur l'API ClientPulse",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
