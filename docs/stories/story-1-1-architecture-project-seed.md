# Story 1.1: Architecture and Project Seed

## Purpose

This is the first story of a three-day classroom RAG course. It does two things, in order:

1. Record the architecture in `docs/architecture.md` and get the instructor's approval.
2. After approval, seed one small application that later stories extend.

Build one application only. Do not build a custom chat frontend or a second demo. Open WebUI is supplied by the trainer and runs separately.

## Prerequisites

- Project path: `docs/config.yaml` did not exist when this story was written, so use the repository root. If it exists when you start, use the project path it configures.
- `docs/architecture.md` did not exist when this story was written. If it exists now, update it. Do not discard what is there.
- No earlier stories exist.
- Python 3.12 and [uv](https://docs.astral.sh/uv/) are installed.
- Supplied raw data and provenance are in `data/raw/`, including `data/raw/PROVENANCE.md`. Preserve every supplied file. Do not edit or delete them.
- Open WebUI bundle: the trainer shares a ZIP over the local LAN. See Part B, step 8.
- Existing work in the repository must be preserved.

## Out of scope

Do not add retrieval, PDF parsing, embeddings, MongoDB provisioning, LLM calls, GraphRAG, agentic RAG, broad deployment, multi-user authorization, a security program, an evaluation harness, or aggressive testing.

## Work to do

### Part A: Architecture (do this first)

Create or update `docs/architecture.md`. Keep it short and in plain English. It must record the following.

**Evidence rules**
- BNS and IPC documents are the only future answer evidence.
- An answer must not claim support without retrieved evidence.
- Identifiers are act-qualified (for example `BNS 103` and `IPC 302`), so the two acts are never confused.
- Supplied provenance is `data/raw/PROVENANCE.md`.
- Retrieved passages are evidence. They are never instructions to the application.

**Trust boundaries (keep light)**
- Validate API input.
- Preserve source origin on every retrieved passage.
- Do not put secrets in code, responses, or logs.

**Fixed choices (later stories reuse these names without renaming and without provider-specific alternatives)**
- Embeddings: Voyage `voyage-3.5`, version `voyage-3.5`, 1,024 dimensions, for every document and query embedding.
- Rerank defaults as listed in `.env.example` below.
- Course modes and model IDs: see "Registry" below.
- Derived corpus files live in `data/processed/` (`bns_sections.jsonl`, `ipc_sections.jsonl`).
- Layout: `src/building_with_rag/`, `tests/`, `data/raw/`, `data/processed/`.

**Contracts (summarised; defined in code in Part B)**
- `POST /v1/query` is the diagnostic endpoint. It owns `QueryResult`.
- `GET /v1/models` and `POST /v1/chat/completions` are the OpenAI-compatible adapter used by Open WebUI. The adapter maps the selected model to the same `QueryRequest` and the same `run_pattern` path as `/v1/query`. It does not duplicate the implementation.
- Open WebUI receives only normal answer text derived from the same `QueryResult`.
- Later stories extend all contracts additively. They never replace them with simplified alternatives, and they do not add parallel top-level fields such as outcome, evidence, answer, confidence, citations, or diagnostics.

**Operational notes**
- `.env` is untracked. Secrets are never committed.
- `MONGODB_URI` is an Atlas free-tier (M0) connection string. The Atlas IP access list must allow your machine.
- `GENERATION_API_BASE_URL` and `GENERATION_API_KEY` are supplied by the trainer for an OpenAI-compatible LiteLLM proxy. Fill them in `.env` only when Story 3.1 needs them.
- A free Voyage key is rate limited, so Story 2.2 embedding takes about 40 minutes.

### Approval gate

When `docs/architecture.md` is ready:

1. Stop.
2. Tell the instructor the architecture is ready for review, and give the file path.
3. Ask for explicit approval.

**Before approval, do not** create seed files, install dependencies, or scaffold code. Resume this same story only after the instructor explicitly approves. If they ask for changes, update the architecture and ask again.

### Part B: Seed (only after approval)

1. **Project.** Create a Python 3.12 + uv project: `pyproject.toml`, `uv.lock`. Dependencies: FastAPI, an ASGI server, Pydantic and pydantic-settings, PyMongo (installed for later use, not used now), Ruff, and a minimal test runner (pytest).
2. **Files.** Create `src/building_with_rag/`, `tests/`, `.env.example`, and `.gitignore` (preserve any existing `.gitignore` content and add to it). Ignore at least `.env`, `.venv/`, `__pycache__/`, and tool caches. Do not ignore `data/raw/`.
3. **`.env.example`.** This is the classroom project's canonical file. Use these exact values:

   ```
   APP_ENV=development
   MONGODB_URI=
   MONGODB_DB_NAME=building_with_rag
   MONGODB_TEST_DB_NAME=building_with_rag_test
   VOYAGE_API_KEY=
   CAPSTONE_API_KEY=
   WEBUI_DEMO_CALLER_ID=demo-public
   GENERATION_API_BASE_URL=
   GENERATION_API_KEY=
   GENERATION_MODEL_NAME=gpt-4o-mini
   RERANK_API_BASE_URL=https://api.voyageai.com/v1
   RERANK_API_KEY=
   RERANK_MODEL_NAME=rerank-2.5
   RERANK_REQUEST_TIMEOUT_SECONDS=30
   RERANK_CANDIDATE_LIMIT=20
   RERANK_SEND_LIMIT=10
   RERANK_RETURN_LIMIT=5
   ```

   Add short comments (in the README section or comments in the file) saying: `.env` is untracked and secrets are never committed; copy `.env.example` to `.env`; the notes on `MONGODB_URI`, the generation proxy, and Voyage rate limits from Part A.
4. **Settings.** Load settings with Pydantic settings from the environment and `.env`. The app must start with no database or model credentials set. Never log or return secret values.
5. **Health.** `GET /healthz` returns a small safe body such as `{"status": "ok"}`. No settings, no secrets, no database call.
6. **Registry.** Create one shared registry of exactly these modes and model IDs, and nothing else:

   | Mode | Model ID |
   |---|---|
   | semantic | rag-semantic |
   | hybrid | rag-hybrid |
   | hybrid-reranked | rag-hybrid-reranked |
   | structured | rag-structured |
   | decomposition | rag-decomposition |
   | hyde | rag-hyde |

   Every mode returns an honest `not_implemented` placeholder (status `not_implemented`, a clear message, empty results) until its own story adds behavior. Provide a single `run_pattern` function that both `/v1/query` and the chat adapter call.
7. **Typed contracts.** Define these as typed Pydantic models, with no behavior, in this project. Later stories reuse the exact names.
   - `QueryRequest`: `question` (1–4,000 characters), `pattern`, optional `caller_id`, optional `SemanticFilters` (`act`, `status`, `access_level`, each a list), `limit` (default 5, range 1–20), `generate_answer` (default false), `required_acts`, `chapter`. The seed may resolve only its fixed local demo caller, but it keeps `caller_id` and does not replace the request shape.
   - `QueryResult`: `pattern`, `status`, `message`, `trace`, `results`, optional `generation`, plus empty-by-default additive fields `omitted_candidates`, `subquestions`, `hyde_direct_candidates`, `hyde_query_candidates`, `hyde_hypothetical_text_debug`. `omitted_candidates` items carry `chunk_id` and `omitted_reason`.
   - `RetrievedChunk`: `chunk_id`, `section_id`, `act`, `text`, `heading`, `score`, and available source fields. Later stories add only the extra fields named in their own handouts (`semantic_score`, `semantic_rank`, `keyword_score`, `keyword_rank`, `fused_score`, `fused_rank`, `rerank_score`, `rerank_rank`).
   - `GenerationResult`: `outcome` (`answered`, `insufficient_evidence`, `unavailable`, `malformed`), `answer`, `claims`, `citations`, `supporting_passages`, `provider`, `model`, `trace`, `context_outcome`, and the confidence fields `confidence`, `draft_answer`, `issues`, `attempts`, `low_confidence_reason`.
   - `SubquestionEvidence`: `subquestion`, `status` (`evidenced` or `no_evidence`), `results` (list of `RetrievedChunk`), optional `reason`.
   - `StructuredSignals`: `intent` (`exact_lookup`, `filter`, or `aggregation`), optional `act`, `section_number`, `chapter`. Story 5.1 fills these in.
   - `ChatCompletionRequest` (text only): `model`, `messages` (roles `system`, `developer`, `user`, `assistant`; text content), `stream`, `n`, and optional strict `rag_options` (`pattern`, list filters, `limit`, `required_acts`, `chapter`). Unknown `rag_options` keys are rejected.
   - OpenAI response and error-envelope models, and a MongoDB-schema contract module (typed document shapes only; no connection or provisioning).
8. **`POST /v1/query`.** Validate with `QueryRequest`, call `run_pattern`, return `QueryResult`. Invalid input returns a normal validation error.
9. **`GET /v1/models`.** Return the six registry model IDs in the OpenAI model-list shape.
10. **`POST /v1/chat/completions`.**
    - Map the selected model to a `QueryRequest` and call the same `run_pattern` as `/v1/query`. Use the latest user message as the question. Set `caller_id` and `generate_answer` on the server (demo caller from `WEBUI_DEMO_CALLER_ID`). Ignore any browser-supplied identity, access level, or generation setting.
    - `stream: false`: return normal OpenAI Chat Completions JSON containing the placeholder text.
    - `stream: true`: return SSE with a role frame, content frame(s), a stop frame, then `data: [DONE]`. No custom event types.
    - Before streaming starts, errors use the OpenAI-style error envelope (`{"error": {"message", "type", ...}}`).
    - Open WebUI gets only normal answer text derived from the `QueryResult`. Do not add diagnostics to the chat reply. Later stories will render final confidence, sources, and low-confidence warnings as clearly labelled text after answer writing, and keep the full `GenerationResult` in `QueryResult.generation`.
11. **Open WebUI (separate client).** Do not build a frontend. The trainer shares the Open WebUI bundle ZIP over the local LAN. Extract it and run the included setup script exactly once before using this project:
    - Windows (primary classroom path), from the extracted bundle root: `powershell -ExecutionPolicy Bypass -File .\setup_open_webui.ps1`
    - macOS/Linux, from the bundle root: `sh setup_open_webui.sh` (needs internet access for its first installation).

    The script installs the pinned Open WebUI version, writes the course settings, starts the loopback-only service, and provisions the RAG options Filter and the Building with RAG Pipe. Do not hand-install Open WebUI, create accounts, edit the admin panel, change either Function, or rerun setup to reload anything. If setup fails, report its exact output and stop. Day-to-day start/stop/status uses the supplied `manage_open_webui` script.

    The pre-provisioned Pipe sends the selected `rag-<pattern>` model, `stream: true`, the latest user message, and normalized `rag_options` (`pattern`, list filters, `limit`, `required_acts`, `chapter`) to the capstone's `/v1/chat/completions`. It never sends identity, access level, or answer-generation settings. The adapter must accept exactly that request.
12. **README.** Add a short README section (or `README.md`) with: setup (`uv sync`, copy `.env.example` to `.env`), run command, the health and placeholder checks, and the Open WebUI smoke check below.

## Completion checks

Keep checks lightweight. Run each of these and record the real command and result:

1. `uv sync` succeeds and `uv.lock` exists.
2. `uv run ruff check .` passes.
3. `uv run pytest` passes. Tests are minimal: health, model list, one placeholder query, one JSON chat, one SSE chat.
4. Start the app with no `.env` and no credentials. It starts.
5. `GET /healthz` returns the safe body.
6. `POST /v1/query` with a valid body (for example pattern `semantic`) returns a `QueryResult` with a `not_implemented` placeholder.
7. `GET /v1/models` lists exactly the six model IDs.
8. `POST /v1/chat/completions` returns the placeholder as JSON (`stream: false`) and as SSE ending in `[DONE]` (`stream: true`).
9. Confirm `.env` is ignored by git, `data/raw/` files are unchanged, and no secrets appear in code or output.
10. **Open WebUI smoke check.** Start the capstone API. Open `http://127.0.0.1:8080`. Select **Building with RAG**. Choose **semantic** in the RAG-options chip. Send a question. The reply must be the capstone's honest placeholder, not a local preview. Record the result.

## Handover

When finished, update this story's section below with:

- **Files created or changed** (actual list).
- **Commands actually run** and their results, including the Open WebUI result. Do not claim a check passed unless you ran it. If a check was skipped, say so and why.
- **Approval:** who approved the architecture and when.
- **Notes for Story 1.2 onward:** anything the next story must know.

Later stories extend the endpoints, models, registry, and `.env.example` additively. They do not rename them or rebuild the UI.

### Completion record

**Files created or changed:** `docs/architecture.md`, `pyproject.toml`, `uv.lock`, `.gitignore` (was empty), `.env.example`, `README.md`, `data/processed/.gitkeep`, `src/building_with_rag/{__init__,config,registry,contracts,mongo_schema,patterns,main}.py`, `tests/test_app.py`.

**Commands run and results:**
1. `uv sync`: OK, `uv.lock` exists. (uv and Python 3.12 were not installed; with the user's OK I ran Astral's installer and `uv python install 3.12`.)
2. `uv run ruff check .`: all checks passed.
3. `uv run pytest`: 7 passed (health, models, query placeholder, query validation, JSON chat, SSE chat, unknown rag_option rejected).
4. Started `uvicorn building_with_rag.main:app --port 8000` with no `.env`: started.
5. `GET /healthz`: `{"status":"ok"}`.
6. `POST /v1/query` (semantic): `not_implemented` QueryResult.
7. `GET /v1/models`: exactly the six IDs.
8. `POST /v1/chat/completions`: placeholder JSON (`stream:false`); SSE with role, content, stop frames and `data: [DONE]` (`stream:true`).
9. `git check-ignore .env`: ignored. No secrets in code. `data/raw/` does not exist in the repo, so there was nothing to verify or preserve.
10. **Open WebUI smoke check: SKIPPED.** The trainer's bundle ZIP is not available here, so I did not install Open WebUI or run its setup script.

**Approval:** the instructor (user) approved `docs/architecture.md` in chat; date not recorded by the tool.

**Notes for Story 1.2 onward:**
- `data/raw/` and `data/raw/PROVENANCE.md` are missing and must be supplied.
- `Pattern` in `contracts.py` is a literal duplicate of `registry.MODES`; update both when adding modes.
- `QueryRequest` uses `filters: SemanticFilters` for the story's "optional SemanticFilters".
- The chat adapter always sets `generate_answer=False` and `caller_id` from `WEBUI_DEMO_CALLER_ID`. Extra top-level chat fields are ignored; unknown `rag_options` keys return a 400 error envelope.
- `httpx` was added as a dependency for the FastAPI TestClient.
