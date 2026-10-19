from pathlib import Path

from docmgmt.namer import DocumentNamer
from docmgmt.rename import rename_file, build_target_path


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeChat:
    def __init__(self, client):
        self.client = client

    def complete(self, *args, **kwargs):
        self.client.calls.append(kwargs)
        return FakeResponse(self.client.content)


class FakeClient:
    def __init__(self, content="Rechnung Strom Versorger 2024"):
        self.content = content
        self.calls = []
        self.chat = FakeChat(self)


def write_doc(tmp_path: Path) -> Path:
    doc = tmp_path / "scan001.txt"
    doc.write_text("Rechnung über Stromrechnung des Versorgers für 2024")
    return doc


def test_suggest_name_returns_sanitized_name(tmp_path):
    doc = write_doc(tmp_path)
    namer = DocumentNamer(FakeClient("Rechnung Strom Versorger 2024"))
    name = namer.suggest_name(doc)
    assert name == "rechnung-strom-versorger-2024"


def test_suggest_name_truncates_to_six_words(tmp_path):
    doc = write_doc(tmp_path)
    namer = DocumentNamer(FakeClient("sehr langer name mit vielen wörtern insgesamt"))
    assert len(namer.suggest_name(doc).split("-")) <= 6


def test_suggest_name_strips_quotes(tmp_path):
    doc = write_doc(tmp_path)
    namer = DocumentNamer(FakeClient('`"uebersicht-plantage"\n'))
    assert namer.suggest_name(doc) == "uebersicht-plantage"


def test_suggest_filename_keeps_suffix(tmp_path):
    doc = write_doc(tmp_path)
    namer = DocumentNamer(FakeClient("Rechnung Strom"))
    assert namer.suggest_filename(doc) == "rechnung-strom.txt"


def test_suggest_name_returns_none_for_empty_text(tmp_path):
    doc = tmp_path / "leer.txt"
    doc.write_text("   ")
    namer = DocumentNamer(FakeClient("egal"))
    assert namer.suggest_name(doc) is None


def test_suggest_name_returns_none_for_missing_file(tmp_path):
    namer = DocumentNamer(FakeClient("egal"))
    assert namer.suggest_name(tmp_path / "gibtsnicht.txt") is None


def test_rename_file(tmp_path):
    doc = write_doc(tmp_path)
    target = rename_file(doc, "rechnung-2024")
    assert target.name == "rechnung-2024.txt"
    assert target.exists()
    assert not doc.exists()


def test_rename_file_dry_run(tmp_path):
    doc = write_doc(tmp_path)
    target = rename_file(doc, "rechnung-2024", dry_run=True)
    assert target == tmp_path / "rechnung-2024.txt"
    assert doc.exists()
    assert not target.exists()


def test_rename_file_collision(tmp_path):
    doc = write_doc(tmp_path)
    (tmp_path / "rechnung-2024.txt").write_text("x")
    try:
        rename_file(doc, "rechnung-2024")
    except FileExistsError:
        assert doc.exists()
    else:
        raise AssertionError("FileExistsError erwartet")


def test_build_target_path_keeps_suffix_and_directory(tmp_path):
    doc = write_doc(tmp_path)
    target = build_target_path(doc, "neu", directory=tmp_path / "sub")
    assert target == tmp_path / "sub" / "neu.txt"
