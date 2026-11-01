"""Suchindex: lokale SQLite-Datenbank für Dokumente mit Volltextsuche."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    content TEXT NOT NULL,
    indexed_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    filename, content, content='documents', content_rowid='id', tokenize='unicode61'
);
CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, filename, content)
    VALUES (new.id, new.filename, new.content);
END;
CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, filename, content)
    VALUES ('delete', old.id, old.filename, old.content);
END;
CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, filename, content)
    VALUES ('delete', old.id, old.filename, old.content);
    INSERT INTO documents_fts(rowid, filename, content)
    VALUES (new.id, new.filename, new.content);
END;
"""


@dataclass
class Document:
    id: int
    path: str
    filename: str
    content: str
    date: Optional[str] = None
    correspondent: Optional[str] = None
    document_type: Optional[str] = None


class SearchIndex:
    """Lokaler Suchindex über SQLite (FTS5)."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SearchIndex":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def add(self, path: Path, content: str, metadata=None, **meta_kwargs) -> int:
        """Nimmt ein Dokument mit optionalen Metadaten in den Index auf.

        Metadaten als DocumentMetadata-Objekt oder als Schlüsselwortargumente
        (date, correspondent, document_type).
        """
        from docmgmt.metadata import DocumentMetadata

        if metadata is None and meta_kwargs:
            metadata = DocumentMetadata(**meta_kwargs)
        date = getattr(metadata, "date", None) if metadata else None
        correspondent = getattr(metadata, "correspondent", None) if metadata else None
        document_type = getattr(metadata, "document_type", None) if metadata else None
        path = Path(path)
        self._migrate_if_needed()
        cur = self._conn.execute(
            """INSERT OR REPLACE INTO documents
               (path, filename, content, date, correspondent, document_type)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(path.resolve()), path.name, content,
             date, correspondent, document_type),
        )
        self._conn.commit()
        return cur.lastrowid

    def _migrate_if_needed(self) -> None:
        """Ergänzt Metadaten-Spalten in älteren Datenbanken."""
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(documents)")}
        missing = [c for c in ("date", "correspondent", "document_type") if c not in columns]
        if missing:
            for column in missing:
                self._conn.execute(f"ALTER TABLE documents ADD COLUMN {column} TEXT")
            self._conn.commit()

    def remove(self, path: Path) -> bool:
        """Entfernt ein Dokument aus dem Index. Gibt True zurück, wenn gelöscht."""
        cur = self._conn.execute(
            "DELETE FROM documents WHERE path = ?", (str(Path(path).resolve()),)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def get(self, path: Path) -> Optional[Document]:
        self._migrate_if_needed()
        row = self._conn.execute(
            "SELECT * FROM documents WHERE path = ?",
            (str(Path(path).resolve()),),
        ).fetchone()
        return self._to_document(row) if row else None

    def search(self, query: str, limit: int = 50, correspondent: Optional[str] = None,
               date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Document]:
        """Volltextsuche, optional gefiltert nach Korrespondent und Zeitraum."""
        query = query.strip()
        if not query:
            return []
        self._migrate_if_needed()
        fts_query = self._to_fts_query(query)
        conditions = ["documents_fts MATCH ?"]
        params = [fts_query]
        if correspondent:
            conditions.append("d.correspondent LIKE ?")
            params.append(f"%{correspondent}%")
        if date_from:
            conditions.append("d.date >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("d.date <= ?")
            params.append(date_to)
        try:
            rows = self._conn.execute(
                """SELECT d.* FROM documents_fts f JOIN documents d ON d.id = f.rowid
                   WHERE """ + " AND ".join(conditions) +
                " ORDER BY rank LIMIT ?",
                (*params, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [self._to_document(r) for r in rows]

    def all_documents(self) -> List[Document]:
        self._migrate_if_needed()
        rows = self._conn.execute(
            "SELECT * FROM documents ORDER BY filename"
        ).fetchall()
        return [self._to_document(r) for r in rows]

    def all_correspondents(self) -> List[str]:
        """Alle bekannten Korrespondenten, alphabetisch sortiert."""
        self._migrate_if_needed()
        rows = self._conn.execute(
            """SELECT DISTINCT correspondent FROM documents
               WHERE correspondent IS NOT NULL AND correspondent != ''
               ORDER BY correspondent"""
        ).fetchall()
        return [r[0] for r in rows]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    @staticmethod
    def _to_document(row: sqlite3.Row) -> Document:
        keys = row.keys()
        return Document(
            id=row["id"], path=row["path"], filename=row["filename"],
            content=row["content"],
            date=row["date"] if "date" in keys else None,
            correspondent=row["correspondent"] if "correspondent" in keys else None,
            document_type=row["document_type"] if "document_type" in keys else None,
        )

    @staticmethod
    def _to_fts_query(query: str) -> str:
        """Macht eine freie Suchanfrage FTS5-tauglich (alle Begriffe als AND-Präfix)."""
        terms = [t for t in query.split() if t]
        return " ".join(f'"{t}"*' for t in terms)
