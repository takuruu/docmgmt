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

## Kernfunktionen (Zielzustand)

1. **Import & Extraktion** – Text aus TXT/MD/CSV/JSON, PDF, DOCX, Bildern (OCR)
2. **Dateibezeichner** – LLM-Namensvorschlag + sicheres Umbenennen ✅ *(umgesetzt: `DocumentNamer`, `rename_file`)*
3. **Batch-Umbenennung** – Ordner rekursiv scannen, Vorschläge sammeln, halb-/vollautomatisch anwenden
4. **Tags & Metadaten** – Kategorien, Datum, Absender etc. per LLM extrahieren
5. **Suchindex** – lokale Datenbank (z.B. SQLite) mit durchsuchbarem Dokumentindex
6. **CLI / Bedienoberfläche** – praktischer Einstieg für den Alltag

## Roadmap (Reihenfolge)

| # | Feature | Status |
|---|---|---|
| 1 | Dateibezeichner (LLM-Namensvorschlag, Umbenennen) | ✅ fertig (PR #1) |
| 2 | Batch-Umbenennung (Ordner scannen, Vorschau, Anwendung) | 🔜 als Nächstes |
| 3 | Tags & Metadaten-Extraktion | geplant |
| 4 | Suchindex (SQLite) | geplant |
| 5 | CLI (`docmgmt scan <ordner>`, `docmgmt rename --dry-run`) | geplant |

## Nicht-Ziele

- Multi-User, Web-Frontend, Cloud-Sync
- Veröffentlichung als Open-Source-Paket (kein PyPI, keine API-Stabilitätsgarantie)
