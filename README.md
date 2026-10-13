# Building with RAG

Course capstone API (FastAPI). See [docs/architecture.md](docs/architecture.md).

## Setup

```
uv sync
copy .env.example .env     # macOS/Linux: cp .env.example .env
```

`.env` is untracked; never commit secrets. The app starts with no credentials.

## Run

```
uv run uvicorn building_with_rag.main:app --port 8000
```

## Checks

```
curl http://127.0.0.1:8000/healthz
curl -X POST http://127.0.0.1:8000/v1/query -H "Content-Type: application/json" -d "{\"question\":\"murder\",\"pattern\":\"semantic\"}"
curl http://127.0.0.1:8000/v1/models
uv run ruff check .
uv run pytest
```

`/v1/query` returns a `not_implemented` placeholder until each pattern's story adds behavior.

## Open WebUI smoke check

Open WebUI is supplied by the trainer (bundle ZIP; run its setup script once, see the story). With the API running, open <http://127.0.0.1:8080>, select **Building with RAG**, choose **semantic** in the RAG-options chip, and send a question. The reply must be the capstone's placeholder.

## Build the section corpus (Story 2.1)

Extracts one JSON record per BNS / IPC section from `data/raw/` into `data/processed/` (reads the PDFs, never edits them):

```
uv run python -m building_with_rag.ingest
```

Add `--dry-run` to preview without writing files. Then check:

1. **Run it.** `bns_sections.jsonl` and `ipc_sections.jsonl` appear in `data/processed/`. The summary prints SHA-256 status, record counts, `needs_review` counts and the flagged records with reasons.
2. **Field check.** The summary prints `field check: OK` per act. It verifies all required fields, `act` / `status` values, `section_id` format, integer `section_number`, string `chapter`, and non-empty `text`.
3. **Spot-check against the PDFs.** Open the first, a middle and the last record of each file (BNS 1, 103, 358; IPC 1, 302, 511) and one section that spans pages (`page_start` != `page_end`, for example `bns:358`), and compare with the PDF.
4. **Run it again.** The files must be unchanged (same line count and hash) with no duplicate `section_id` values:

```
Get-FileHash data\processed\*.jsonl     # PowerShell; macOS/Linux: sha256sum data/processed/*.jsonl
uv run python -m building_with_rag.ingest
Get-FileHash data\processed\*.jsonl
```
