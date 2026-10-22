# docmgmt – Projektziel & Roadmap

## Ziel

docmgmt wird ein **vollständiges, privates Dokumentmanagementsystem (DMS)**:
Dateien werden importiert, analysiert, per LLM (Mistral-API) sinnvoll benannt,
verschlagwortet und durchsuchbar gemacht.

**Nutzer:** rein privat – Fokus auf Nutzen und einfache Bedienung,
nicht auf Veröffentlichung/Support für Dritte.

**Zentrale Prinzipien:**
- LLM-gestützte Analyse (Mistral Chat API + OCR)
- Lokale Dateien bleiben lokale Dateien – das DMS verwaltet, es verwahrt nicht in einer Cloud
- Keine zerstörerischen Operationen ohne Sicherung (dry-run, Kollisionsschutz)
- **Suche als Kernstück:** integrierte Dokumente müssen schnell auffindbar sein (Suchindex); Import mit automatischem Umbenennen und Batch-Umbenennung unterstützen das

## Kernfunktionen (Zielzustand)

1. **Import & Extraktion** – Text aus TXT/MD/CSV/JSON, PDF, DOCX, Bildern (OCR)
2. **Dateibezeichner** – LLM-Namensvorschlag + sicheres Umbenennen ✅ *(umgesetzt: `DocumentNamer`, `rename_file`)*
3. **Batch-Umbenennung** – Ordner rekursiv scannen, Vorschläge sammeln, halb-/vollautomatisch anwenden
4. **Suchindex & Suche** – lokales Herzstück: integrierte Dokumente schnell finden (SQLite-Volltextindex)
5. **Import mit Auto-Umbenennung** – Importfunktion, die Dateien automatisch analysiert, benennt und indexiert
6. **Tags & Metadaten** – Korrespondent (mit wem), Datum etc. per LLM extrahieren; sortierte Ansichten nach Korrespondent und Datum
7. **CLI** – praktischer Einstieg für den Alltag (`docmgmt scan <ordner>`)
8. **GUI** – grafische Oberfläche als GTK-4-App (PyGObject), passend zur XFCE-Desktop-Umgebung; Fensterstruktur: Toolbar + Dateiliste + Detailbereich, erster GUI-Dialog: Batch-Umbenennung (Vorschlag pro Datei, übernehmen/verwerfen, Sammel-Aktion); später Suchleiste und sortierte Ansichten (Korrespondent/Datum)

## Roadmap (Reihenfolge)

| # | Feature | Status |
|---|---|---|
| 1 | Dateibezeichner (LLM-Namensvorschlag, Umbenennen) | ✅ fertig (PR #1) |
| 2 | Batch-Umbenennung (Ordner scannen, Vorschau, Anwendung) | ✅ fertig (PR #2) |
| 3 | Import mit Auto-Umbenennung (analysieren → benennen → indexieren) | 🔜 in Arbeit |
| 3 | Import mit Auto-Umbenennung (analysieren → benennen → indexieren) | geplant |
| 4 | Suchindex & Suche (SQLite-Volltextindex, schnelles Finden) | geplant (Kernstück) |
| 5 | Tags & Metadaten (Korrespondent, Datum; sortierte Ansichten) | 🟣 in Arbeit (Extraktion via Document-Annotation, im Index gespeichert, GUI zeigt sie; sortierte Ansichten folgen) |
| 6 | CLI (`docmgmt scan <ordner>`, `docmgmt rename --dry-run`) | geplant |
| 7 | GTK-4-GUI (PyGObject) für XFCE | 🟣 in Arbeit (Basis: Toolbar + Dateiliste + Detail, Batch-Dialog, Suche) |

## Rahmenbedingungen

- **GUI:** GTK 4 mit PyGObject (XFCE-Desktop; bewusst kein Qt/Tkinter/libadwaita). Die Bibliothek bleibt UI-unabhängig – GUI und CLI sind nur Bedenschichten darüber.

## Nicht-Ziele

- Multi-User, Web-Frontend, Cloud-Sync
- Veröffentlichung als Open-Source-Paket (kein PyPI, keine API-Stabilitätsgarantie)
