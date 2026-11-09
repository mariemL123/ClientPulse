
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.rate_limiter import limiter

from app.config import settings
from app.routers.users import router as users_router
from app.routers.dashboard import router as dashboard_router
from app.routers.auth import router as auth_router
from app.routers.client import router as clients_router
from app.routers.ticket import router as tickets_router


app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Ajoute les en-t?tes HTTP de s?curit? aux r?ponses."""

    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )

    # HSTS est r?serv? ? la production servie exclusivement en HTTPS.
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000"

    return response


# Configuration de la limitation des requ?tes.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configuration CORS centralisée.
# En production, seules les origines HTTPS déclarées sont autorisées.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
    ],
)

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
