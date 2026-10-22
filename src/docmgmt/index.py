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

    def add(self, path: Path, content: str) -> int:
        """Nimmt ein Dokument in den Index auf (Pfad muss einzigartig sein)."""
        path = Path(path)
        cur = self._conn.execute(
            "INSERT OR REPLACE INTO documents (path, filename, content) VALUES (?, ?, ?)",
            (str(path.resolve()), path.name, content),
        )
        self._conn.commit()
        return cur.lastrowid

    def remove(self, path: Path) -> bool:
        """Entfernt ein Dokument aus dem Index. Gibt True zurück, wenn gelöscht."""
        cur = self._conn.execute(
            "DELETE FROM documents WHERE path = ?", (str(Path(path).resolve()),)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def get(self, path: Path) -> Optional[Document]:
        row = self._conn.execute(
            "SELECT id, path, filename, content FROM documents WHERE path = ?",
            (str(Path(path).resolve()),),
        ).fetchone()
        return self._to_document(row) if row else None

    def search(self, query: str, limit: int = 50) -> List[Document]:
        """Volltextsuche über Dateiname und Inhalt."""
        query = query.strip()
        if not query:
            return []
        fts_query = self._to_fts_query(query)
        try:
            rows = self._conn.execute(
                """SELECT d.id, d.path, d.filename, d.content
                   FROM documents_fts f JOIN documents d ON d.id = f.rowid
                   WHERE documents_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (fts_query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [self._to_document(r) for r in rows]

    def all_documents(self) -> List[Document]:
        rows = self._conn.execute(
            "SELECT id, path, filename, content FROM documents ORDER BY filename"
        ).fetchall()
        return [self._to_document(r) for r in rows]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    @staticmethod
    def _to_document(row: sqlite3.Row) -> Document:
        return Document(id=row["id"], path=row["path"], filename=row["filename"],
                        content=row["content"])

    @staticmethod
    def _to_fts_query(query: str) -> str:
        """Macht eine freie Suchanfrage FTS5-tauglich (alle Begriffe als AND-Präfix)."""
        terms = [t for t in query.split() if t]
        return " ".join(f'"{t}"*' for t in terms)
