"""Hilfsfunktionen zum Umbenennen von Dateien."""
from __future__ import annotations

from pathlib import Path
from typing import Optional


def build_target_path(source: Path, new_name: str, directory: Optional[Path] = None) -> Path:
    """Baut den Zielpfad aus neuem Namen und alter Endung."""
    directory = Path(directory) if directory is not None else source.parent
    return directory / f"{new_name}{source.suffix}"


def rename_file(source: Path, new_name: str, dry_run: bool = False) -> Optional[Path]:
    """Benennt eine Datei um. Gibt den neuen Pfad zurück, bei dry_run None."""
    target = build_target_path(source, new_name)
    if target == source:
        return source
    if target.exists():
        raise FileExistsError(f"Ziel existiert bereits: {target}")
    if dry_run:
        return target
    source.rename(target)
    return target
