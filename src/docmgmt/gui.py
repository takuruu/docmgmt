"""Qt-6-GUI (PySide6) für docmgmt – passend zum KDE-Plasma-Desktop.

Fensterstruktur: Toolbar + Dateiliste + Detailbereich.
Dialog: Batch-Umbenennung (Vorschlag pro Datei, übernehmen/verwerfen,
Sammel-Aktion). Suchleiste über den lokalen Suchindex (SQLite FTS5).

Start: `docmgmt-gui` oder `python -m docmgmt.gui`.
"""
from __future__ import annotations

import html
import threading
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from docmgmt.batch import RenameSuggestion, apply_suggestions, collect_suggestions
from docmgmt.client import create_mistral_client
from docmgmt.index import SearchIndex
from docmgmt.namer import DocumentNamer


class DocumentRow(QWidget):
    """Eine Zeile in der Dateiliste: Dateiname + Metadaten + Pfad."""

    def __init__(self, doc):
        super().__init__()
        self.doc = doc
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(1)

        name = QLabel(doc.filename)
        name_font = name.font()
        name_font.setBold(True)
        name.setFont(name_font)
        layout.addWidget(name)

        meta_parts = []
        if getattr(doc, "date", None):
            meta_parts.append(doc.date)
        if getattr(doc, "correspondent", None):
            meta_parts.append(doc.correspondent)
        if getattr(doc, "document_type", None):
            meta_parts.append(doc.document_type)
        small = self.font()
        small.setPointSizeF(max(small.pointSizeF() * 0.85, 8.0))
        if meta_parts:
            meta = QLabel("  ·  ".join(meta_parts))
            meta.setFont(small)
            layout.addWidget(meta)
        path = QLabel(doc.path)
        path.setFont(small)
        layout.addWidget(path)


class BatchRenameDialog(QDialog):
    """Dialog für die Batch-Umbenennung: Vorschlag pro Datei, übernehmen/verwerfen."""

    collected = Signal(object, object)
    renamed = Signal()

    def __init__(self, namer: DocumentNamer, directory: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Batch-Umbenennung – {directory.name}")
        self.resize(760, 500)
        self.namer = namer
        self.directory = Path(directory)
        self.suggestions: List[RenameSuggestion] = []
        self.items: List[QTreeWidgetItem] = []
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["✓", "Datei", "Vorschlag"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().resizeSection(0, 32)
        self.tree.header().setSectionResizeMode(1, self.tree.header().ResizeToContents)
        layout.addWidget(self.tree, 1)

        self.status = QLabel("Scanne Ordner …")
        layout.addWidget(self.status)

        self.buttons = QDialogButtonBox()
        cancel = self.buttons.addButton("Abbrechen", QDialogButtonBox.ButtonRole.RejectRole)
        self.apply_btn = self.buttons.addButton(
            "Ausgewählte umbenennen", QDialogButtonBox.ButtonRole.AcceptRole)
        self.apply_btn.setEnabled(False)
        layout.addWidget(self.buttons)
        cancel.clicked.connect(self.reject)
        self.apply_btn.clicked.connect(self._on_apply)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.collected.connect(self._fill)

        threading.Thread(target=self._collect, daemon=True).start()

    def _collect(self) -> None:
        try:
            result = collect_suggestions(self.namer, self.directory)
            suggestions, error = result.planned, None
        except Exception as exc:
            suggestions, error = [], str(exc)
        self.collected.emit(suggestions, error)

    def _fill(self, suggestions: List[RenameSuggestion], error: Optional[str]) -> None:
        self._loading = True
        self.suggestions = suggestions
        for s in suggestions:
            item = QTreeWidgetItem()
            if s.error:
                item.setText(1, s.source.name)
                item.setText(2, f"Fehler: {s.error}")
                item.setToolTip(1, str(s.source))
                item.setToolTip(2, s.error)
            else:
                flags = (Qt.ItemIsEnabled | Qt.ItemIsSelectable
                         | Qt.ItemIsUserCheckable)
                item.setFlags(flags)
                item.setCheckState(
                    0, Qt.Checked if s.is_rename else Qt.Unchecked)
                item.setText(1, s.source.name)
                item.setText(2, s.suggested_filename or s.source.name)
                item.setToolTip(1, str(s.source))
            self.tree.addTopLevelItem(item)
            self.items.append(item)
        renamed = sum(1 for s in suggestions if s.is_rename)
        self.status.setText(
            error or f"{len(suggestions)} Dateien gefunden, "
                     f"{renamed} Umbenennungen vorgeschlagen.")
        self._loading = False
        self._update_apply()

    def _on_item_changed(self, _item, _column) -> None:
        if not self._loading:
            self._update_apply()

    def _checked(self) -> List[RenameSuggestion]:
        return [s for s, item in zip(self.suggestions, self.items)
                if item.flags() & Qt.ItemIsUserCheckable
                and item.checkState(0) == Qt.Checked]

    def _update_apply(self) -> None:
        self.apply_btn.setEnabled(bool(self._checked()))

    def _on_apply(self) -> None:
        selected = self._checked()
        if not selected:
            return
        result = apply_suggestions(selected)
        summary = (f"{len(result.renamed)} umbenannt, {len(result.skipped)} übersprungen, "
                   f"{len(result.failed)} fehlgeschlagen.")
        self.status.setText(summary)
        self.apply_btn.setEnabled(False)
        for item in self.items:
            item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
        if result.renamed:
            self.renamed.emit()


class MainWindow(QMainWindow):
    """Hauptfenster: Toolbar + Dateiliste + Detailbereich."""

    importDone = Signal(str)

    def __init__(self, index: SearchIndex, namer: Optional[DocumentNamer],
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("docmgmt")
        self.resize(1000, 650)
        self.index = index
        self.namer = namer
        self.documents: List = []

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        toolbar = QHBoxLayout()
        outer.addLayout(toolbar)

        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Dokumente durchsuchen …")
        self.search_entry.setClearButtonEnabled(True)
        self.search_entry.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_entry, 1)

        self.import_btn = QPushButton("Import")
        self.import_btn.clicked.connect(self._on_import)
        toolbar.addWidget(self.import_btn)

        self.batch_btn = QPushButton("Batch-Umbenennung")
        self.batch_btn.clicked.connect(self._on_batch)
        toolbar.addWidget(self.batch_btn)

        if namer is None:
            self.import_btn.setEnabled(False)
            self.batch_btn.setEnabled(False)
            self.search_entry.setPlaceholderText(
                "MISTRAL_API_KEY nicht gesetzt – Suche trotzdem möglich")

        splitter = QSplitter(Qt.Horizontal)
        outer.addWidget(splitter, 1)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(360)
        self.list_widget.currentRowChanged.connect(self._on_row_selected)
        splitter.addWidget(self.list_widget)

        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(False)
        self.detail.setPlainText("Kein Dokument ausgewählt.")
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 580])

        self.importDone.connect(self._on_import_done)
        self._refresh()

    def _refresh(self, query: str = "") -> None:
        self.documents = (self.index.search(query) if query.strip()
                          else self.index.all_documents())
        self.list_widget.clear()
        for doc in self.documents:
            item = QListWidgetItem()
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, DocumentRow(doc))
        if not self.documents:
            self.detail.setPlainText("Kein Dokument ausgewählt.")

    def _on_search(self, text: str) -> None:
        self._refresh(text.strip())

    def _on_row_selected(self, row: int) -> None:
        if row < 0 or row >= len(self.documents):
            return
        doc = self.documents[row]
        excerpt = doc.content[:1500] if doc.content else "(kein Text)"
        esc = html.escape
        meta_lines = []
        if getattr(doc, "date", None):
            meta_lines.append(f"Datum: {esc(doc.date)}")
        if getattr(doc, "correspondent", None):
            meta_lines.append(f"Korrespondent: {esc(doc.correspondent)}")
        if getattr(doc, "document_type", None):
            meta_lines.append(f"Art: {esc(doc.document_type)}")
        parts = [f"<p><b>{esc(doc.filename)}</b></p>"]
        if meta_lines:
            parts.append("<p>" + "<br>".join(meta_lines) + "</p>")
        parts.append(f"<p>{esc(doc.path)}</p>")
        parts.append("<p>" + esc(excerpt).replace("\n", "<br>") + "</p>")
        self.detail.setHtml("".join(parts))

    def _on_import(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Ordner zum Importieren wählen")
        if folder:
            threading.Thread(target=self._import_worker,
                             args=(Path(folder),), daemon=True).start()

    def _import_worker(self, folder: Path) -> None:
        from docmgmt.importer import Importer

        results = Importer(self.namer, self.index).import_directory(folder)
        summary = (f"{len(results)} Dateien importiert, "
                  f"{sum(1 for r in results if r.error)} Fehler.")
        self.importDone.emit(summary)

    def _on_import_done(self, summary: str) -> None:
        self._refresh(self.search_entry.text().strip())
        QMessageBox.information(self, "docmgmt", summary)

    def _on_batch(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Ordner für Batch-Umbenennung wählen")
        if not folder:
            return
        dlg = BatchRenameDialog(self.namer, Path(folder), parent=self)
        dlg.renamed.connect(lambda: self._refresh(self.search_entry.text().strip()))
        dlg.exec()


class DocmgmtApp:
    """Qt-Anwendung: hält Index und Namer vor, erzeugt das Hauptfenster."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.index: Optional[SearchIndex] = None
        self.namer: Optional[DocumentNamer] = None

    def run(self) -> int:
        self.index = SearchIndex(self.db_path)
        try:
            self.namer = DocumentNamer(create_mistral_client())
        except Exception:
            self.namer = None
        app = QApplication.instance() or QApplication([])
        win = MainWindow(self.index, self.namer)
        win.show()
        return app.exec()


def main() -> int:
    """Einstiegspunkt: `docmgmt-gui`."""
    import argparse

    parser = argparse.ArgumentParser(description="docmgmt Qt-6-Oberfläche (KDE Plasma)")
    parser.add_argument("--db", default="~/.local/share/docmgmt/index.db",
                        help="Pfad zur SQLite-Indexdatenbank")
    args = parser.parse_args()
    db_path = Path(args.db).expanduser()
    return DocmgmtApp(db_path).run()


if __name__ == "__main__":
    raise SystemExit(main())
