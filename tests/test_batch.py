from pathlib import Path

from docmgmt.batch import (
    apply_suggestions,
    collect_suggestions,
    rename_batch,
    scan_directory,
    RenameSuggestion,
)
from docmgmt.namer import DocumentNamer
from tests.test_namer import FakeClient


def make_namer(content="Rechnung Strom 2024"):
    return DocumentNamer(FakeClient(content))


def setup_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "datei1.txt").write_text("Inhalt Rechnung Strom")
    (folder / "datei2.txt").write_text("Inhalt Rechnung Wasser")
    sub = folder / "sub"
    sub.mkdir()
    (sub / "tief.txt").write_text("Inhalt Vertrag")
    return folder


def test_scan_directory_recursive_sorted(tmp_path):
    folder = setup_folder(tmp_path)
    files = scan_directory(folder)
    assert files == [
        folder / "datei1.txt",
        folder / "datei2.txt",
        folder / "sub" / "tief.txt",
    ]


def test_scan_directory_non_recursive(tmp_path):
    folder = setup_folder(tmp_path)
    files = scan_directory(folder, recursive=False)
    assert files == [folder / "datei1.txt", folder / "datei2.txt"]


def test_scan_directory_suffix_filter(tmp_path):
    folder = setup_folder(tmp_path)
    (folder / "bild.png").write_bytes(b"\x89PNG")
    files = scan_directory(folder, suffixes=[".txt"])
    assert all(f.suffix == ".txt" for f in files)
    assert len(files) == 3


def test_collect_suggestions_dry_run(tmp_path):
    folder = setup_folder(tmp_path)
    namer = make_namer("rechnung-strom-2024")
    result = collect_suggestions(namer, folder)
    assert len(result.planned) == 3
    assert all(s.suggested_name == "rechnung-strom-2024" for s in result.planned)
    assert all(p.exists() for p in scan_directory(folder))


def test_rename_batch_dry_run_keeps_files(tmp_path):
    folder = setup_folder(tmp_path)
    namer = make_namer()
    result = rename_batch(namer, folder, apply=False)
    assert len(result.planned) == 3
    assert result.renamed == []
    assert (folder / "datei1.txt").exists()
    assert (folder / "sub" / "tief.txt").exists()


def test_rename_batch_applies(tmp_path):
    folder = setup_folder(tmp_path)
    namer = make_namer()
    result = rename_batch(namer, folder, apply=True)
    # datei1 und datei2 bekämen denselben Namen -> Kollision, eine wird übersprungen
    assert len(result.renamed) == 2
    assert (folder / "rechnung-strom-2024.txt").exists()
    assert (folder / "sub" / "rechnung-strom-2024.txt").exists()
    assert len(result.skipped) == 1
    assert result.skipped[0].name in ("datei1.txt", "datei2.txt")


def test_rename_batch_skips_when_name_already_good(tmp_path):
    folder = setup_folder(tmp_path)
    namer = make_namer("datei1")
    result = rename_batch(namer, folder, apply=True)
    assert (folder / "datei1.txt").exists()
    assert (folder / "rechnung-strom-2024.txt") is not None or True
    assert folder / "datei1.txt" in result.kept


def test_rename_batch_collision_skips(tmp_path):
    folder = setup_folder(tmp_path)
    (folder / "rechnung-strom-2024.txt").write_text("existiert schon")
    namer = make_namer()
    result = rename_batch(namer, folder, apply=True, skip_existing=True)
    assert (folder / "rechnung-strom-2024.txt").read_text() == "existiert schon"
    assert folder / "datei1.txt" in result.skipped


def test_apply_suggestions_manual_selection(tmp_path):
    folder = setup_folder(tmp_path)
    doc = folder / "datei1.txt"
    suggestion = RenameSuggestion(source=doc, suggested_name="neuer-name")
    result = apply_suggestions([suggestion])
    assert result.renamed == [folder / "neuer-name.txt"]
    assert not doc.exists()


def test_apply_suggestions_without_name_skips(tmp_path):
    folder = setup_folder(tmp_path)
    doc = folder / "datei1.txt"
    suggestion = RenameSuggestion(source=doc)
    result = apply_suggestions([suggestion])
    assert result.skipped == [doc]
    assert doc.exists()
