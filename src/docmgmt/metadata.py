"""Metadaten-Extraktion: Datum, Korrespondent, Dokumentart.

Nutzt für Bilder und PDFs die Mistral-OCR-Document-Annotation
(`document_annotation_format`), für textbasierte Formate den Chat-Endpoint
mit JSON-Ausgabe. Das Ergebnis wird konsistent normalisiert.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from docmgmt.extraction import IMAGE_SUFFIXES, _image_mime

ANNOTATION_PROMPT = (
    "Extrahiere die Metadaten dieses Dokuments: das Dokumentdatum "
    "(Format YYYY-MM-DD, leer wenn unbekannt), den Korrespondenten "
    "(Absender oder Empfänger, z. B. Firmen- oder Personenname) und "
    "die Art des Dokuments (z. B. rechnung, vertrag, brief, rechnung-strom). "
    "Antworte ausschließlich gemäß dem vorgegebenen Schema."
)

ANNOTATION_JSON_SCHEMA = {
    "name": "document_metadata",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Dokumentdatum im Format YYYY-MM-DD, leerer String wenn unbekannt",
            },
            "correspondent": {
                "type": "string",
                "description": "Absender oder Empfänger des Dokuments, leerer String wenn unbekannt",
            },
            "document_type": {
                "type": "string",
                "description": "Art des Dokuments, z. B. rechnung, vertrag, brief, leerer String wenn unbekannt",
            },
        },
        "required": ["date", "correspondent", "document_type"],
        "additionalProperties": False,
    },
}

CHAT_PROMPT = (
    "Du extrahierst Metadaten aus Dokumenttexten. Gib ausschließlich ein "
    "JSON-Objekt mit den Schlüsseln \"date\" (YYYY-MM-DD, leerer String wenn "
    "unbekannt), \"correspondent\" (Absender oder Empfänger) und "
    "\"document_type\" (z. B. rechnung, vertrag, brief) zurück. "
    "Keine Erklärungen, nur JSON.\n\nDokumenttext:\n"
)


@dataclass
class DocumentMetadata:
    """Normalisierte Metadaten eines Dokuments."""
    date: Optional[str] = None
    correspondent: Optional[str] = None
    document_type: Optional[str] = None


def extract_metadata(path: Path, mistral_client, model: str = "mistral-small-latest") -> Optional[DocumentMetadata]:
    """Extrahiert Datum, Korrespondent und Dokumentart aus einer Datei.

    Bilder/PDFs: OCR mit Document-Annotation. Sonst: Chat mit JSON-Ausgabe.
    Gibt None zurück, wenn keine Metadaten bestimmbar sind.
    """
    path = Path(path)
    if mistral_client is None or not path.is_file():
        return None
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES or suffix == ".pdf":
        raw = _annotate_via_ocr(path, mistral_client)
    else:
        raw = _annotate_via_chat(path, mistral_client, model)
    return _parse_annotation(raw)


def _annotate_via_ocr(path: Path, client) -> Optional[dict]:
    import base64

    try:
        data = base64.b64encode(path.read_bytes()).decode("utf-8")
        if path.suffix.lower() == ".pdf":
            document = {"type": "document_url",
                        "document_url": f"data:application/pdf;base64,{data}"}
        else:
            mime = _image_mime(path)
            document = {"type": "image_url",
                        "image_url": f"data:{mime};base64,{data}"}
        response = client.ocr.process(
            model="mistral-ocr-latest",
            document=document,
            document_annotation_format={"type": "json_schema",
                                        "json_schema": ANNOTATION_JSON_SCHEMA},
            document_annotation_prompt=ANNOTATION_PROMPT,
        )
        raw = getattr(response, "document_annotation", None)
    except Exception:
        return None
    return _loads(raw)


def _annotate_via_chat(path: Path, client, model: str) -> Optional[dict]:
    from docmgmt.extraction import extract_text

    text = extract_text(path)
    if not text or not text.strip():
        return None
    try:
        response = client.chat.complete(
            model=model,
            messages=[{"role": "user", "content": CHAT_PROMPT + text[:6000]}],
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
    except Exception:
        return None
    return _loads(raw)


def _loads(raw) -> Optional[dict]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _parse_annotation(data) -> Optional[DocumentMetadata]:
    if not isinstance(data, dict):
        data = _loads(data)
    if not data:
        return None
    date = _normalize_date(data.get("date"))
    correspondent = _clean(data.get("correspondent"))
    document_type = _clean(data.get("document_type"))
    if not any([date, correspondent, document_type]):
        return None
    return DocumentMetadata(date=date, correspondent=correspondent,
                            document_type=document_type)


def _clean(value) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:200] or None


def _normalize_date(value) -> Optional[str]:
    """Normalisiert ein Datum auf ISO (YYYY-MM-DD), sonst None."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    return match.group(0) if match else None
