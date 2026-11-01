"""Tests für die Qt-6-GUI (PySide6) – überspringen, wenn PySide6 fehlt."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets", reason="PySide6 nicht installiert")

from docmgmt.gui import BatchRenameDialog, DocmgmtApp, MainWindow
from docmgmt.index import SearchIndex


@pytest.fixture()
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_gui_module_importable():
    assert DocmgmtApp is not None
    assert BatchRenameDialog is not None


def test_main_window_lists_documents(qapp, tmp_path):
    index = SearchIndex(tmp_path / "index.db")
    index.add(tmp_path / "rechnung-strom-2026.txt", "Stromrechnung Beispieltext",
              date="2026-01-15", correspondent="Stadtwerke")
    win = MainWindow(index, None)
    assert win.list_widget.count() == 1
    win.list_widget.setCurrentRow(0)
    assert "rechnung-strom-2026.txt" in win.detail.toPlainText()
    assert "Stadtwerke" in win.detail.toPlainText()
    assert "Datum: 2026-01-15" in win.detail.toPlainText()


def test_main_window_search_filters(qapp, tmp_path):
    index = SearchIndex(tmp_path / "index.db")
    index.add(tmp_path / "alpha.txt", "Inhalt Alpha Versicherung")
    index.add(tmp_path / "beta.txt", "Inhalt Beta Steuer")
    win = MainWindow(index, None)
    assert win.list_widget.count() == 2
    win._refresh("steuer")
    assert win.list_widget.count() == 1
