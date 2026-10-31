
from fastapi import FastAPI
from app.routers.dashboard import router as dashboard_router
from app.database import Base, engine
from app.models.client import Client
from app.models.ticket import Ticket
from app.routers.client import router as clients_router
from app.routers.ticket import router as tickets_router


app = FastAPI(
    title="ClientPulse API",
    description="API de gestion des clients et des réclamations.",
    version="0.2.0",
)

# Enregistrement des tables SQLAlchemy dans SQLite.
Base.metadata.create_all(bind=engine)

# Enregistrement des routes REST.
app.include_router(clients_router)
app.include_router(tickets_router)
app.include_router(dashboard_router)

@app.get("/")
def root():
    return {
        "message": "Bienvenue sur l'API ClientPulse",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
