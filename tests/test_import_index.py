import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from docmgmt.importer import Importer
from docmgmt.index import SearchIndex
from docmgmt.namer import DocumentNamer
from test_namer import FakeClient


def make_importer(tmp_path, content="Rechnung Strom 2024"):
    index = SearchIndex(tmp_path / "index.db")
    namer = DocumentNamer(FakeClient(content))
    return Importer(namer, index), index


def test_import_file_renames_and_indexes(tmp_path):
    importer, index = make_importer(tmp_path)
    doc = tmp_path / "scan001.txt"
    doc.write_text("Stromrechnung Versorger 2024")

    result = importer.import_file(doc)

    assert result.error is None
    assert result.renamed
    assert result.imported_path == tmp_path / "rechnung-strom-2024.txt"
    assert not doc.exists()
    assert index.count() == 1
    assert index.get(tmp_path / "rechnung-strom-2024.txt") is not None


def test_import_file_into_target_dir(tmp_path):
    importer, index = make_importer(tmp_path)
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    archive = tmp_path / "archiv"
    doc = incoming / "scan001.txt"
    doc.write_text("Stromrechnung")

    result = importer.import_file(doc, target_dir=archive)

    assert result.imported_path == archive / "rechnung-strom-2024.txt"
    assert result.imported_path.exists()
    assert not doc.exists()
    assert index.get(archive / "rechnung-strom-2024.txt") is not None


def test_import_file_without_rename_keeps_name(tmp_path):
    importer, index = make_importer(tmp_path, content="wichtiger-vertrag")
    doc = tmp_path / "x.txt"
    doc.write_text("Vertragstext")

    result = importer.import_file(doc, rename=False)

    assert result.renamed is False
    assert result.imported_path == doc
    assert doc.exists()
    assert index.count() == 1


def test_import_file_collision_aborts(tmp_path):
    importer, _ = make_importer(tmp_path)
    (tmp_path / "rechnung-strom-2024.txt").write_text("existiert")
    doc = tmp_path / "scan001.txt"
    doc.write_text("Stromrechnung")

    result = importer.import_file(doc)

    assert result.error is not None
    assert "existiert bereits" in result.error
    assert doc.exists()
    assert importer.index.count() == 0


def test_import_file_missing(tmp_path):
    importer, _ = make_importer(tmp_path)
    result = importer.import_file(tmp_path / "gibtsnicht.txt")
    assert result.error == "Datei nicht gefunden"


def test_import_directory(tmp_path):
    importer, index = make_importer(tmp_path, content="vertrag-versicherung")
    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "a.txt").write_text("Vertrag")
    (folder / "b.md").write_text("Versicherung")

    results = importer.import_directory(folder)

    assert len(results) == 2
    assert all(r.error is None for r in results)
    assert index.count() == 2
    assert not (folder / "a.txt").exists()
    assert (folder / "vertrag-versicherung.txt").exists()


def test_index_search_by_content(tmp_path):
    importer, index = make_importer(tmp_path)
    doc = tmp_path / "scan001.txt"
    doc.write_text("Die Stromrechnung des Versorgers für das Jahr 2024")
    importer.import_file(doc, rename=False)

    hits = index.search("Stromrechnung")

    assert len(hits) == 1
    assert hits[0].filename == "scan001.txt"
    assert "Stromrechnung" in hits[0].content


def test_index_search_multiple_terms_and(tmp_path):
    importer, index = make_importer(tmp_path)
    (tmp_path / "a.txt").write_text("Rechnung fuer Strom")
    (tmp_path / "b.txt").write_text("Rechnung fuer Wasser")
    importer.import_file(tmp_path / "a.txt", rename=False)
    importer.import_file(tmp_path / "b.txt", rename=False)

    assert len(index.search("strom")) == 1
    assert len(index.search("rechnung")) == 2


def test_index_search_empty_query(tmp_path):
    _, index = make_importer(tmp_path)
    assert index.search("   ") == []


def test_index_remove(tmp_path):
    importer, index = make_importer(tmp_path)
    doc = tmp_path / "a.txt"
    doc.write_text("Inhalt")
    importer.import_file(doc, rename=False)

    assert index.remove(doc) is True
    assert index.count() == 0
    assert index.remove(doc) is False


def test_index_reimport_updates(tmp_path):
    importer, index = make_importer(tmp_path)
    doc = tmp_path / "a.txt"
    doc.write_text("Erste Fassung")
    importer.import_file(doc, rename=False)
    doc.write_text("Zweite Fassung mit anderem Inhalt")
    importer.import_file(doc, rename=False)

    assert index.count() == 1
    assert len(index.search("Zweite")) == 1
    assert index.search("Erste") == []
