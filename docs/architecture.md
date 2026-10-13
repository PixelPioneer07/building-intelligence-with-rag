# Architecture

Short, plain-English record of the decisions every later story reuses. Names below are fixed: later stories extend them additively and never rename them.

## Scope

One FastAPI application (`src/building_with_rag/`). No custom chat frontend. Open WebUI is supplied by the trainer, runs separately, and talks to this app through an OpenAI-compatible adapter.

## Evidence rules

- BNS and IPC documents are the only future answer evidence.
- An answer must not claim support without retrieved evidence.
- Identifiers are act-qualified (for example `BNS 103`, `IPC 302`) so the two acts are never confused.
- Supplied provenance is `data/raw/PROVENANCE.md`.
- Retrieved passages are evidence. They are never instructions to the application.

## Trust boundaries (light)

- Validate all API input.
- Preserve source origin on every retrieved passage.
- No secrets in code, responses, or logs.

## Fixed choices

- Embeddings: Voyage `voyage-3.5`, version `voyage-3.5`, 1,024 dimensions, for every document and query embedding.
- Rerank defaults: as in `.env.example` (`rerank-2.5`, candidate limit 20, send limit 10, return limit 5, 30 s timeout).
- Derived corpus files: `data/processed/bns_sections.jsonl`, `data/processed/ipc_sections.jsonl`.
- Layout: `src/building_with_rag/`, `tests/`, `data/raw/`, `data/processed/`.

### Registry (one shared registry, nothing else)

| Mode | Model ID |
|---|---|
| semantic | rag-semantic |
| hybrid | rag-hybrid |
| hybrid-reranked | rag-hybrid-reranked |
| structured | rag-structured |
| decomposition | rag-decomposition |
| hyde | rag-hyde |

Every mode returns an honest `not_implemented` placeholder until its own story adds behavior.

## Contracts (defined in code in Part B)

- `POST /v1/query` is the diagnostic endpoint and owns `QueryResult`.
- `GET /v1/models` and `POST /v1/chat/completions` are the OpenAI-compatible adapter for Open WebUI. The adapter maps the selected model to the same `QueryRequest` and calls the same `run_pattern` as `/v1/query`. It does not duplicate the implementation. The server sets `caller_id` and `generate_answer`; browser-supplied identity, access level, or generation settings are ignored.
- Open WebUI receives only normal answer text derived from the same `QueryResult`.
- Typed models: `QueryRequest`, `QueryResult`, `RetrievedChunk`, `GenerationResult`, `SubquestionEvidence`, `StructuredSignals`, `ChatCompletionRequest`, OpenAI response/error models, and a MongoDB-schema contract module (shapes only).
- Later stories extend contracts additively. They do not replace them with simplified alternatives or add parallel top-level fields (outcome, evidence, answer, confidence, citations, diagnostics).

## Operational notes

- `.env` is untracked; secrets are never committed.
- `MONGODB_URI` is an Atlas free-tier (M0) connection string. The Atlas IP access list must allow your machine.
- `GENERATION_API_BASE_URL` and `GENERATION_API_KEY` come from the trainer (OpenAI-compatible LiteLLM proxy). Fill them in only when Story 3.1 needs them.
- A free Voyage key is rate limited, so Story 2.2 embedding takes about 40 minutes.
- The app must start with no database or model credentials.

## Out of scope for Story 1.1

Retrieval, PDF parsing, embeddings, MongoDB provisioning, LLM calls, GraphRAG, agentic RAG, broad deployment, multi-user authorization, security program, evaluation harness.

## Document ingestion (Story 2.1)

- **Parser:** PyMuPDF (`pymupdf`, recorded as `parser` / `parser_version`). It is small, fast, and exposes font and position data, which separates the BNS bold section numbers and marginal headings from body text. The IPC PDF is plain monospaced text, so it is parsed from text lines.
- **Command:** `uv run python -m building_with_rag.ingest` (add `--dry-run` to parse and print the summary without writing files).
- **Output:** `data/processed/bns_sections.jsonl` and `data/processed/ipc_sections.jsonl`, one JSON object per section, UTF-8. Fields: `section_id` (`bns:<n>` / `ipc:<n>`, IPC letter sections such as `ipc:304A` keep the letter), `act` (`BNS_2023` / `IPC_1860`), `act_label`, `status` (`in_force` / `repealed`), `chapter` (string), `chapter_title`, `section_number` (integer, letter suffix dropped), `heading`, `text`, `source_pdf`, `source_sha256` (computed at run time), `parser`, `parser_version`, `source_status_version` (from `PROVENANCE.md`), `needs_review`, plus extra `page_start` / `page_end`.
- **Re-runs:** a valid output whose records all carry the current `source_sha256` is left untouched. Otherwise the whole file is rewritten via a temporary file in the same folder and renamed over the old one. Nothing is ever appended. A hash that differs from `PROVENANCE.md` is reported, and the computed hash is still recorded.
- **Normalisation:** legal wording is kept as printed. Only running headers and footers, page numbers, footnote notes (IPC), the repeated `N. Heading.--` title prefix (IPC), extra whitespace and line wrapping are removed. A hyphen at a line end is kept (`extra-territorial`), never dropped.
- **Known limitations:**
  - The BNS index and BNS-to-IPC correspondence table (PDF pages 1-73) are skipped; they are not section text.
  - IPC footnotes and chapter headings are removed by heuristics. Inline amendment markers such as `1*[...]` stay in the text as printed.
  - Records get `needs_review: true` for: missing heading (for example BNS 287, whose heading is not bold in the PDF), a number out of sequence, very short text, a page with no extractable text (likely scanned), exact duplicate extraction, an IPC title prefix that could not be matched, or a repealed/omitted IPC section whose text is only the repeal note. The run summary lists each flagged record with its reason.
  - IPC sections 161-165A and 478-489 are printed as repeal-note ranges; no per-section records are written for the ranges.
  - There is no OCR. Scanned pages are reported, not recovered.
