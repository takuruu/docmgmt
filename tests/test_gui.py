"""Tests für die GTK-4-GUI – überspringen, wenn PyGObject fehlt."""
from __future__ import annotations

import importlib
import pytest

gi = pytest.importorskip("gi", reason="PyGObject/PyGObject nicht installiert")
gi.require_version("Gtk", "4.0")


def test_gui_module_importable():
    mod = importlib.import_module("docmgmt.gui")
    assert hasattr(mod, "DocmgmtApp")
    assert hasattr(mod, "BatchRenameDialog")
