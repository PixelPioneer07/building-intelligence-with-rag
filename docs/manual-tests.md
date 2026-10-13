# Manual tests

## Story 1.1 — Architecture and Project Seed

Adds the FastAPI seed: `/healthz`, `/v1/query`, and the OpenAI-compatible `/v1/models` and `/v1/chat/completions`. Every pattern returns an honest `not_implemented` placeholder.

Prerequisite: start the API with `uv run uvicorn building_with_rag.main:app --port 8000`. No `.env` is needed. The commands use bash-style quoting (Git Bash, macOS, Linux).

```bash
curl http://127.0.0.1:8000/healthz
```

Expected: `{"status":"ok"}`.

```bash
curl http://127.0.0.1:8000/v1/models
```

Expected: a model list with exactly `rag-semantic`, `rag-hybrid`, `rag-hybrid-reranked`, `rag-structured`, `rag-decomposition`, `rag-hyde`.

```bash
curl -X POST http://127.0.0.1:8000/v1/query -H 'Content-Type: application/json' -d '{"question":"What is the punishment for murder?","pattern":"semantic"}'
curl -X POST http://127.0.0.1:8000/v1/query -H 'Content-Type: application/json' -d '{"question":"What is the punishment for murder?","pattern":"hybrid"}'
curl -X POST http://127.0.0.1:8000/v1/query -H 'Content-Type: application/json' -d '{"question":"What is the punishment for murder?","pattern":"hybrid-reranked"}'
curl -X POST http://127.0.0.1:8000/v1/query -H 'Content-Type: application/json' -d '{"question":"What is the punishment for murder?","pattern":"structured"}'
curl -X POST http://127.0.0.1:8000/v1/query -H 'Content-Type: application/json' -d '{"question":"What is the punishment for murder?","pattern":"decomposition"}'
curl -X POST http://127.0.0.1:8000/v1/query -H 'Content-Type: application/json' -d '{"question":"What is the punishment for murder?","pattern":"hyde"}'
```

Expected: each returns a `QueryResult` with `pattern` set to the requested mode, `status` `not_implemented`, a clear `message`, and empty `results`.

```bash
curl -X POST http://127.0.0.1:8000/v1/query -H 'Content-Type: application/json' -d '{"question":"","pattern":"semantic"}'
```

Expected: HTTP 422 validation error (empty question).

```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"rag-semantic","stream":false,"messages":[{"role":"user","content":"What is the punishment for murder?"}]}'
```

Expected: a `chat.completion` JSON whose message content is the semantic not-implemented placeholder.

```bash
curl -N -X POST http://127.0.0.1:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"rag-semantic","stream":true,"messages":[{"role":"user","content":"What is the punishment for murder?"}],"rag_options":{"pattern":"semantic","limit":5}}'
```

Expected: SSE frames (role, content, stop) and the response ends with `data: [DONE]`.

```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"rag-unknown","messages":[{"role":"user","content":"hi"}]}'
```

Expected: HTTP 404 with an OpenAI-style `{"error": {"message", "type", ...}}` envelope.
