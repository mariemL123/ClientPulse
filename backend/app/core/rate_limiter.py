"""Configuration de la limitation des tentatives de connexion."""

from slowapi import Limiter
from slowapi.util import get_remote_address


# Limitation basée sur l'adresse IP du client.
# Le stockage mémoire est adapté au serveur local à un seul processus.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
)
