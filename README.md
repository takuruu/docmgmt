# docmgmt

Python-Bibliothek zur Dokumentanalyse: extrahiert Text aus Dateien und schlägt über die Mistral-API sinnvolle Dateinamen vor.

## Installation

```bash
pip install -e .
# optionale Extraktions-Backends:
pip install -e ".[pdf,docx]"
```

## Verwendung

```python
from docmgmt.client import create_mistral_client
from docmgmt.namer import DocumentNamer
from docmgmt.rename import rename_file

client = create_mistral_client()  # liest MISTRAL_API_KEY
namer = DocumentNamer(client)

new_name = namer.suggest_name("scan001.pdf")   # z.B. "rechnung-strom-2024"
new_path = rename_file(Path("scan001.pdf"), new_name)
```

## Unterstützte Formate

- **Text**: `.txt`, `.md`, `.csv`, `.json`, `.xml`, `.html`, `.log`, `.yml`, `.yaml`, `.rst`
- **PDF**: `.pdf` (via `pypdf`, optional)
- **DOCX**: `.docx` (via `python-docx`, optional)
- **Bilder**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp`, `.tiff` — OCR über `mistral-ocr-latest`

## Module

| Modul | Zweck |
|---|---|
| `docmgmt.extraction` | Textextraktion aus Dateien (inkl. Bild-OCR via Mistral) |
| `docmgmt.namer` | `DocumentNamer`: LLM-Namensvorschlag via Mistral Chat API |
| `docmgmt.rename` | Umbenennen mit Kollisionsschutz und `dry_run` |
| `docmgmt.batch` | Batch-Umbenennung: Ordner scannen, Vorschläge sammeln, anwenden |
| `docmgmt.client` | Mistral-Client-Factory (`MISTRAL_API_KEY`) |

## Batch-Umbenennung

```python
from docmgmt.client import create_mistral_client
from docmgmt.batch import rename_batch

client = create_mistral_client()

# Dry-Run: nur Vorschläge sammeln
result = rename_batch(client_namer, "~/Dokumente/Scans")
for s in result.needs_rename:
    print(s.source.name, "->", s.suggested_filename)

# Anwenden (überspringt Ziele, die bereits existieren)
result = rename_batch(client_namer, "~/Dokumente/Scans", apply=True)
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```
