"""GTK-4-GUI (PyGObject) für docmgmt.

Fensterstruktur: Toolbar + Dateiliste + Detailbereich.
Erster Dialog: Batch-Umbenennung (Vorschlag pro Datei, übernehmen/verwerfen,
Sammel-Aktion). Suchleiste über den lokalen Suchindex (SQLite FTS5).

Start: `docmgmt-gui` oder `python -m docmgmt.gui`.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import List, Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from docmgmt.batch import RenameSuggestion, apply_suggestions, collect_suggestions
from docmgmt.client import create_mistral_client
from docmgmt.index import SearchIndex
from docmgmt.namer import DocumentNamer


class DocumentRow(Gtk.Box):
    """Eine Zeile in der Dateiliste: Dateiname + Pfad."""

    def __init__(self, doc):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.doc = doc
        name = Gtk.Label(label=doc.filename, halign=Gtk.Align.START,
                         ellipsize=3, xalign=0)
        self.append(name)
        meta_parts = []
        if getattr(doc, "date", None):
            meta_parts.append(doc.date)
        if getattr(doc, "correspondent", None):
            meta_parts.append(doc.correspondent)
        if getattr(doc, "document_type", None):
            meta_parts.append(doc.document_type)
        if meta_parts:
            meta = Gtk.Label(label="  ·  ".join(meta_parts), halign=Gtk.Align.START,
                             ellipsize=3, xalign=0, css_classes=["caption", "dim-label"])
            self.append(meta)
        path = Gtk.Label(label=doc.path, halign=Gtk.Align.START,
                         ellipsize=3, xalign=0, css_classes=["caption", "dim-label"])
        self.append(path)


class BatchRenameDialog(Gtk.Dialog):
    """Dialog für die Batch-Umbenennung: Vorschlag pro Datei, übernehmen/verwerfen."""

    def __init__(self, parent, namer: DocumentNamer, directory: Path):
        super().__init__(transient_for=parent, modal=True,
                         title=f"Batch-Umbenennung – {directory.name}")
        self.set_default_size(720, 480)
        self.namer = namer
        self.directory = Path(directory)
        self.suggestions: List[RenameSuggestion] = []
        self.checks: List[Gtk.CheckButton] = []

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content = self.get_content_area()
        content.append(box)

        scrolled = Gtk.ScrolledWindow(vexpand=True, min_content_height=300)
        box.append(scrolled)
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.set_child(self.list_box)

        self.status = Gtk.Label(label="Scanne Ordner …", halign=Gtk.Align.START,
                                css_classes=["dim-label"])
        box.append(self.status)

        self.add_button("Abbrechen", Gtk.ResponseType.CANCEL)
        self.apply_btn = self.add_button("Ausgewählte umbenennen", Gtk.ResponseType.APPLY)
        self.apply_btn.set_sensitive(False)
        self.connect("response", self._on_response)

        threading.Thread(target=self._collect, daemon=True).start()

    def _collect(self) -> None:
        try:
            result = collect_suggestions(self.namer, self.directory)
            suggestions = result.planned
            error = None
        except Exception as exc:
            suggestions, error = [], str(exc)
        GLib.idle_add(self._fill, suggestions, error)

    def _fill(self, suggestions: List[RenameSuggestion], error: Optional[str]) -> None:
        self.suggestions = suggestions
        for s in suggestions:
            row = Gtk.ListBoxRow()
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            check = Gtk.CheckButton(active=s.is_rename)
            if s.error:
                label = Gtk.Label(label=f"{s.source.name}  –  Fehler: {s.error}",
                                  ellipsize=3, hexpand=True, xalign=0)
                check.set_active(False)
                check.set_sensitive(False)
            else:
                label = Gtk.Label(
                    label=f"{s.source.name}  →  {s.suggested_filename or s.source.name}",
                    ellipsize=3, hexpand=True, xalign=0)
            hbox.append(check)
            hbox.append(label)
            row.set_child(hbox)
            self.list_box.append(row)
            self.checks.append(check)
            check.connect("toggled", self._update_apply)
        renamed = sum(1 for s in suggestions if s.is_rename)
        self.status.set_text(
            error or f"{len(suggestions)} Dateien gefunden, {renamed} Umbenennungen vorgeschlagen.")
        self.apply_btn.set_sensitive(renamed > 0)
        self._update_apply()

    def _update_apply(self, *_args) -> None:
        self.apply_btn.set_sensitive(any(c.get_active() for c in self.checks
                                         if c.get_sensitive()))

    def _on_response(self, _dlg, response: int) -> None:
        if response != Gtk.ResponseType.APPLY:
            return
        selected = [s for s, c in zip(self.suggestions, self.checks)
                    if c.get_sensitive() and c.get_active()]
        result = apply_suggestions(selected)
        summary = (f"{len(result.renamed)} umbenannt, {len(result.skipped)} übersprungen, "
                   f"{len(result.failed)} fehlgeschlagen.")
        self.status.set_text(summary)
        self.apply_btn.set_sensitive(False)
        for c in self.checks:
            c.set_sensitive(False)


class MainWindow(Gtk.ApplicationWindow):
    """Hauptfenster: Toolbar + Dateiliste + Detailbereich."""

    def __init__(self, app, index: SearchIndex, namer: DocumentNamer):
        super().__init__(application=app, title="docmgmt")
        self.set_default_size(1000, 650)
        self.index = index
        self.namer = namer
        self.documents: List = []

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(outer)

        header = Gtk.HeaderBar()
        outer.append(header)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                          margin_top=6, margin_bottom=6, margin_start=6, margin_end=6)
        outer.append(toolbar)

        self.search_entry = Gtk.SearchEntry(
            placeholder_text="Dokumente durchsuchen …", hexpand=True)
        self.search_entry.connect("search-changed", self._on_search)
        toolbar.append(self.search_entry)

        import_btn = Gtk.Button(label="Import")
        import_btn.connect("clicked", self._on_import)
        toolbar.append(import_btn)

        batch_btn = Gtk.Button(label="Batch-Umbenennung")
        batch_btn.connect("clicked", self._on_batch)
        toolbar.append(batch_btn)

        if namer is None:
            import_btn.set_sensitive(False)
            batch_btn.set_sensitive(False)
            self.search_entry.set_placeholder_text(
                "MISTRAL_API_KEY nicht gesetzt – Suche trotzdem möglich")

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL,
                          vexpand=True, wide_handle=True)
        outer.append(paned)

        scrolled = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        paned.set_start_child(scrolled)
        paned.set_position(420)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scrolled.set_child(self.list_box)

        self.detail = Gtk.Label(label="Kein Dokument ausgewählt.",
                                wrap=True, valign=Gtk.Align.START, halign=Gtk.Align.START,
                                margin_top=8, margin_bottom=8, margin_start=8, margin_end=8)
        detail_scroll = Gtk.ScrolledWindow()
        detail_scroll.set_child(self.detail)
        paned.set_end_child(detail_scroll)

        self.list_box.connect("row-selected", self._on_row_selected)
        self._refresh()

    def _refresh(self, query: str = "") -> None:
        self.documents = (self.index.search(query) if query.strip()
                          else self.index.all_documents())
        child = self.list_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.list_box.remove(child)
            child = nxt
        for doc in self.documents:
            row = Gtk.ListBoxRow()
            row.set_child(DocumentRow(doc))
            self.list_box.append(row)
        if not self.documents:
            self.detail.set_text("Kein Dokument ausgewählt.")

    def _on_search(self, entry) -> None:
        self._refresh(entry.get_text().strip())

    def _on_row_selected(self, _box, row) -> None:
        if row is None:
            return
        doc = self.documents[row.get_index()]
        excerpt = doc.content[:1500] if doc.content else "(kein Text)"
        meta_lines = []
        if getattr(doc, "date", None):
            meta_lines.append(f"Datum: {doc.date}")
        if getattr(doc, "correspondent", None):
            meta_lines.append(f"Korrespondent: {doc.correspondent}")
        if getattr(doc, "document_type", None):
            meta_lines.append(f"Art: {doc.document_type}")
        meta_block = "\n".join(meta_lines)
        parts = [f"<b>{GLib.markup_escape_text(doc.filename)}</b>"]
        if meta_block:
            parts.append(GLib.markup_escape_text(meta_block))
        parts.append(GLib.markup_escape_text(doc.path))
        parts.append(GLib.markup_escape_text(excerpt))
        self.detail.set_markup("\n\n".join(parts))

    def _pick_folder(self, title: str, callback) -> None:
        dialog = Gtk.FileChooserNative(
            title=title, action=Gtk.FileChooserAction.SELECT_FOLDER,
            transient_for=self, modal=True)
        dialog.connect("response", callback)
        dialog.show()

    def _on_import(self, _btn) -> None:
        self._pick_folder("Ordner zum Importieren wählen", self._import_folder)

    def _import_folder(self, dialog, response: int) -> None:
        if response != Gtk.ResponseType.ACCEPT:
            dialog.destroy()
            return
        folder = dialog.get_file().get_path()
        dialog.destroy()
        threading.Thread(target=self._import_worker, args=(Path(folder),),
                         daemon=True).start()

    def _import_worker(self, folder: Path) -> None:
        from docmgmt.importer import Importer

        results = Importer(self.namer, self.index).import_directory(folder)
        summary = (f"{len(results)} Dateien importiert, "
                  f"{sum(1 for r in results if r.error)} Fehler.")
        GLib.idle_add(self._refresh)
        GLib.idle_add(self._show_toast, summary)

    def _on_batch(self, _btn) -> None:
        self._pick_folder("Ordner für Batch-Umbenennung wählen", self._batch_folder)

    def _batch_folder(self, dialog, response: int) -> None:
        if response != Gtk.ResponseType.ACCEPT:
            dialog.destroy()
            return
        folder = Path(dialog.get_file().get_path())
        dialog.destroy()
        dlg = BatchRenameDialog(self, self.namer, folder)
        dlg.present()
        dlg.connect("destroy", lambda *_: self._refresh())

    def _show_toast(self, message: str) -> None:
        dlg = Gtk.MessageDialog(transient_for=self, modal=True,
                                 message_type=Gtk.MessageType.INFO,
                                 buttons=Gtk.ButtonsType.OK, text=message)
        dlg.connect("response", lambda d, *_: d.destroy())
        dlg.present()


class DocmgmtApp(Gtk.Application):
    def __init__(self, db_path: Path):
        super().__init__(application_id="io.github.takuruu.docmgmt")
        self.db_path = Path(db_path)
        self.index: Optional[SearchIndex] = None
        self.namer: Optional[DocumentNamer] = None

    def do_activate(self) -> None:
        if self.index is None:
            self.index = SearchIndex(self.db_path)
            try:
                self.namer = DocumentNamer(create_mistral_client())
            except Exception:
                self.namer = None
        win = MainWindow(self, self.index, self.namer)
        self.add_window(win)
        win.present()


def main() -> int:
    """Einstiegspunkt: `docmgmt-gui`."""
    import argparse

    parser = argparse.ArgumentParser(description="docmgmt GTK-4-Oberfläche")
    parser.add_argument("--db", default="~/.local/share/docmgmt/index.db",
                        help="Pfad zur SQLite-Indexdatenbank")
    args = parser.parse_args()
    db_path = Path(args.db).expanduser()
    return DocmgmtApp(db_path).run(None)


if __name__ == "__main__":
    raise SystemExit(main())
