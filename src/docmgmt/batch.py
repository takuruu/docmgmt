"""Batch-Umbenennung: Ordner scannen, Vorschläge sammeln, sicher anwenden."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

from docmgmt.namer import DocumentNamer
from docmgmt.rename import rename_file


@dataclass
class RenameSuggestion:
    """Vorschlag für eine Datei: alter Pfad, neuer Basisname."""
    source: Path
    suggested_name: Optional[str] = None
    error: Optional[str] = None

    @property
    def suggested_filename(self) -> Optional[str]:
        if not self.suggested_name:
            return None
        return f"{self.suggested_name}{self.source.suffix}"

    @property
    def is_rename(self) -> bool:
        return self.suggested_filename is not None and self.suggested_filename != self.source.name


@dataclass
class BatchResult:
    """Ergebnis eines Batch-Laufs."""
    planned: List[RenameSuggestion] = field(default_factory=list)
    renamed: List[Path] = field(default_factory=list)
    skipped: List[Path] = field(default_factory=list)
    failed: List[Path] = field(default_factory=list)

    @property
    def needs_rename(self) -> List[RenameSuggestion]:
        return [s for s in self.planned if s.is_rename]

    @property
    def kept(self) -> List[Path]:
        """Dateien, deren Name bereits passend ist oder ohne Vorschlag."""
        return [s.source for s in self.planned if not s.is_rename]


def scan_directory(directory: Path, recursive: bool = True, suffixes: Optional[Iterable[str]] = None) -> List[Path]:
    """Sammelt Dateien aus einem Ordner, optional gefiltert nach Endungen."""
    directory = Path(directory)
    pattern = "**/*" if recursive else "*"
    files = [p for p in sorted(directory.glob(pattern)) if p.is_file()]
    if suffixes:
        allowed = {s.lower() if s.startswith(".") else f".{s.lower()}" for s in suffixes}
        files = [p for p in files if p.suffix.lower() in allowed]
    return files


def collect_suggestions(namer: DocumentNamer, directory: Path, recursive: bool = True,
                        suffixes: Optional[Iterable[str]] = None) -> BatchResult:
    """Scannt den Ordner und sammelt Namensvorschläge (keine Umbenennung)."""
    result = BatchResult()
    for path in scan_directory(directory, recursive=recursive, suffixes=suffixes):
        suggestion = RenameSuggestion(source=path)
        try:
            suggestion.suggested_name = namer.suggest_name(path)
        except Exception as exc:
            suggestion.error = str(exc)
        result.planned.append(suggestion)
    return result


def apply_suggestions(suggestions: List[RenameSuggestion], skip_existing: bool = True) -> BatchResult:
    """Wendet die übergebenen (ausgewählten) Vorschläge an."""
    result = BatchResult()
    for s in suggestions:
        if not s.is_rename or not s.suggested_name:
            result.skipped.append(s.source)
            continue
        try:
            result.renamed.append(rename_file(s.source, s.suggested_name))
        except FileExistsError:
            if skip_existing:
                result.skipped.append(s.source)
            else:
                result.failed.append(s.source)
        except OSError:
            result.failed.append(s.source)
    return result


def rename_batch(namer: DocumentNamer, directory: Path, recursive: bool = True,
                 suffixes: Optional[Iterable[str]] = None, apply: bool = False,
                 skip_existing: bool = True) -> BatchResult:
    """Kompletter Batch-Lauf: scannen, Vorschläge sammeln, optional anwenden.

    Ohne apply=True ist der Lauf ein Dry-Run (nur Vorschläge).
    """
    result = collect_suggestions(namer, directory, recursive=recursive, suffixes=suffixes)
    if apply:
        applied = apply_suggestions(result.needs_rename, skip_existing=skip_existing)
        result.renamed = applied.renamed
        result.skipped.extend(applied.skipped)
        result.failed = applied.failed
    return result
