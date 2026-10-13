import json

from fastapi.testclient import TestClient

from building_with_rag.main import app
from building_with_rag.registry import MODEL_IDS

client = TestClient(app)


def test_health():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_models():
    ids = [m["id"] for m in client.get("/v1/models").json()["data"]]
    assert ids == list(MODEL_IDS) and len(ids) == 6


def test_query_placeholder():
    r = client.post("/v1/query", json={"question": "murder?", "pattern": "semantic"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "not_implemented" and body["results"] == []


def test_query_invalid():
    assert client.post("/v1/query", json={"question": "", "pattern": "semantic"}).status_code == 422


def _chat(**extra):
    return {"model": "rag-semantic", "messages": [{"role": "user", "content": "hi"}], **extra}


def test_chat_json():
    r = client.post("/v1/chat/completions", json=_chat())
    assert r.status_code == 200
    assert "not implemented" in r.json()["choices"][0]["message"]["content"]


def test_chat_sse():
    r = client.post(
        "/v1/chat/completions",
        json=_chat(stream=True, rag_options={"pattern": "semantic", "limit": 5}),
    )
    frames = [x for x in r.text.split("\n\n") if x]
    assert frames[-1] == "data: [DONE]"
    assert json.loads(frames[0][6:])["choices"][0]["delta"] == {"role": "assistant"}
    assert json.loads(frames[-2][6:])["choices"][0]["finish_reason"] == "stop"


def test_chat_rejects_unknown_rag_option():
    r = client.post("/v1/chat/completions", json=_chat(rag_options={"caller_id": "x"}))
    assert r.status_code == 400 and "error" in r.json()
