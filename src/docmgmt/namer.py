"""Namensvorschläge für Dokumente per Mistral-API."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from docmgmt.extraction import extract_text

SYSTEM_PROMPT = (
    "Du benennst Dateien anhand ihres Inhalts. Analysiere den folgenden "
    "Dokumentinhalt und schlage einen prägnanten, aussagekräftigen Dateinamen vor. "
    "Antworte ausschließlich mit dem Dateinamen ohne Erklärung, ohne Anführungszeichen "
    "und ohne Dateiendung. Verwende Kleinbuchstaben, Wörter getrennt durch Bindestriche, "
    "maximal 6 Wörter, keine Sonderzeichen außer Bindestrichen."
)

DEFAULT_MODEL = "mistral-small-latest"


class DocumentNamer:
    """Ermittelt über die Mistral-API einen sinnvollen Namen für ein Dokument."""

    def __init__(self, client, model: str = DEFAULT_MODEL):
        self.client = client
        self.model = model

    def suggest_name(self, path: Path) -> Optional[str]:
        """Schlägt einen neuen Basisnamen (ohne Endung) für die Datei vor."""
        path = Path(path)
        if not path.is_file():
            return None
        text = extract_text(path, mistral_client=self.client)
        if not text or not text.strip():
            return None
        content = self._complete(text)
        if content is None:
            return None
        return self._sanitize(content) or None

    def suggest_filename(self, path: Path) -> Optional[str]:
        """Schlägt einen vollständigen Dateinamen inkl. Endung vor."""
        name = self.suggest_name(path)
        if name is None:
            return None
        return f"{name}{Path(path).suffix}"

    def _complete(self, text: str) -> Optional[str]:
        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0.2,
            )
        except Exception:
            return None
        choices = getattr(response, "choices", None)
        if not choices:
            return None
        return choices[0].message.content

    @staticmethod
    def _sanitize(name: str) -> str:
        name = name.strip().strip("`\"'")
        match = re.search(r"[A-Za-zÄÖÜäöüß0-9].*[A-Za-zÄÖÜäöüß0-9]", name)
        if match:
            name = match.group(0)
        name = name.lower()
        name = re.sub(r"[^a-z0-9äöüß-]+", "-", name)
        name = re.sub(r"-{2,}", "-", name).strip("-")
        words = name.split("-")
        if len(words) > 6:
            name = "-".join(words[:6])
        return name
