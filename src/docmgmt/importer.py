"""Import: Datei analysieren, per LLM benennen und in den Suchindex aufnehmen."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from docmgmt.extraction import extract_text
from docmgmt.index import SearchIndex
from docmgmt.namer import DocumentNamer
from docmgmt.rename import build_target_path


@dataclass
class ImportResult:
    """Ergebnis eines Imports."""
    source: Path
    imported_path: Optional[Path] = None
    document_id: Optional[int] = None
    renamed: bool = False
    error: Optional[str] = None


class Importer:
    """Importiert Dateien: extrahieren, umbenennen, indexieren."""

    def __init__(self, namer: DocumentNamer, index: SearchIndex):
        self.namer = namer
        self.index = index

    def import_file(self, source: Path, target_dir: Optional[Path] = None,
                    rename: bool = True, overwrite: bool = False) -> ImportResult:
        """Importiert eine Datei in target_dir (Default: gleicher Ordner).

        Schritte: Text extrahieren → LLM-Namen vorschlagen → Datei verschieben/umbenennen
        → in den Suchindex aufnehmen.
        """
        source = Path(source)
        result = ImportResult(source=source)
        if not source.is_file():
            result.error = "Datei nicht gefunden"
            return result

        text = extract_text(source, mistral_client=self.namer.client)
        if not text or not text.strip():
            result.error = "Kein Text extrahierbar"
            return result

        destination = source
        if rename:
            suggested = self.namer._complete(text)
            if suggested:
                name = self.namer._sanitize(suggested)
                if name:
                    candidate = build_target_path(source, name, directory=target_dir)
                    if candidate != source:
                        if candidate.exists() and not overwrite:
                            result.error = f"Ziel existiert bereits: {candidate}"
                            return result
                        if target_dir is not None:
                            target_dir.mkdir(parents=True, exist_ok=True)
                            candidate.parent.mkdir(parents=True, exist_ok=True)
                            source.replace(candidate)
                        else:
                            source.rename(candidate)
                        destination = candidate
                        result.renamed = True

        result.imported_path = destination
        result.document_id = self.index.add(destination, text)
        return result

    def import_directory(self, directory: Path, target_dir: Optional[Path] = None,
                         rename: bool = True, overwrite: bool = False,
                         suffixes: Optional[List[str]] = None) -> List[ImportResult]:
        """Importiert alle Dateien eines Ordners (nicht-rekursiv in Unterverzeichnisse)."""
        from docmgmt.batch import scan_directory

        results = []
        for path in scan_directory(directory, recursive=False, suffixes=suffixes):
            results.append(self.import_file(path, target_dir=target_dir, rename=rename,
                                           overwrite=overwrite))
        return results
