"""Tests für Metadaten-Extraktion (Datum, Korrespondent, Dokumentart)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from docmgmt.metadata import (
    DocumentMetadata,
    _normalize_date,
    _parse_annotation,
    extract_metadata,
)


class FakeChatResponse:
    def __init__(self, content):
        class Msg:
            pass
        msg = Msg()
        msg.content = content
        self.choices = [type("Choice", (), {"message": msg})()]


class FakeChatClient:
    """Chat-Client-Mock: gibt die JSON-Antwort aus dem übergebenen Text zurück."""
    def __init__(self, payload):
        self.payload = payload

        class Chat:
            def complete(inner_self, model, messages, response_format=None, **kw):
                text = messages[0]["content"]
                user = json.loads(text.split("Dokumenttext:\n")[-1])
                return FakeChatResponse(json.dumps(user))
        self.chat = Chat()


def test_parse_annotation_full():
    meta = _parse_annotation({"date": "2024-03-15", "correspondent": "Stadtwerke",
                              "document_type": "rechnung"})
    assert meta == DocumentMetadata(date="2024-03-15", correspondent="Stadtwerke",
                                    document_type="rechnung")


def test_parse_annotation_empty_returns_none():
    assert _parse_annotation({"date": "", "correspondent": "", "document_type": ""}) is None
    assert _parse_annotation(None) is None


def test_parse_annotation_wrapped_json_string():
    raw = 'Hier ist dein JSON: {"date": "01.02.2024", "correspondent": "A", "document_type": "brief"} Ende'
    meta = _parse_annotation(json.loads(json.dumps(raw)))
    assert meta is not None
    assert meta.date == "2024-02-01"


def test_normalize_date_formats():
    assert _normalize_date("15.03.2024") == "2024-03-15"
    assert _normalize_date("2024/03/15") == "2024-03-15"
    assert _normalize_date("Datum: 2024-03-15") == "2024-03-15"
    assert _normalize_date("") is None
    assert _normalize_date("nicht vorhanden") is None


def test_extract_metadata_via_chat(tmp_path: Path):
    doc = tmp_path / "brief.txt"
    doc.write_text('Dokumenttext:\n{"date": "15.03.2024", "correspondent": "Stadtwerke", "document_type": "rechnung"}', encoding="utf-8")
    client = FakeChatClient(None)
    meta = extract_metadata(doc, client)
    assert meta is not None
    assert meta.date == "2024-03-15"
    assert meta.correspondent == "Stadtwerke"
    assert meta.document_type == "rechnung"


def test_extract_metadata_no_client(tmp_path: Path):
    doc = tmp_path / "x.txt"
    doc.write_text("hallo", encoding="utf-8")
    assert extract_metadata(doc, None) is None
