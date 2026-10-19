"""Factory für den Mistral-Client."""
from __future__ import annotations

import os


def create_mistral_client(api_key: str = None):
    """Erstellt einen Mistral-Client aus dem API-Key oder der Umgebung."""
    try:
        from mistralai import Mistral
    except ImportError:
        from mistralai.client import Mistral

    api_key = api_key or os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError(
            "Kein Mistral-API-Key gefunden. Setze MISTRAL_API_KEY oder übergib api_key."
        )
    return Mistral(api_key=api_key)
