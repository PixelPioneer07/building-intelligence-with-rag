import json
import time
import uuid
from collections.abc import Iterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from building_with_rag.config import get_settings
from building_with_rag.contracts import (
    ChatChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatResponseMessage,
    ErrorBody,
    ErrorEnvelope,
    ModelCard,
    ModelList,
    QueryRequest,
    QueryResult,
    SemanticFilters,
)
from building_with_rag.patterns import run_pattern
from building_with_rag.registry import MODEL_IDS, MODEL_TO_MODE

app = FastAPI(title="Building with RAG")


def error_response(status: int, message: str, type_: str, param: str | None = None):
    body = ErrorEnvelope(error=ErrorBody(message=message, type=type_, param=param))
    return JSONResponse(status_code=status, content=body.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = json.loads(json.dumps(exc.errors(), default=str))
    if request.url.path.startswith("/v1/chat/"):
        first = errors[0] if errors else {}
        loc = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
        message = f"{loc}: {first.get('msg', 'invalid request')}"
        return error_response(400, message, "invalid_request_error", loc or None)
    return JSONResponse(status_code=422, content={"detail": errors})


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/query", response_model=QueryResult)
def query(request: QueryRequest) -> QueryResult:
    return run_pattern(request)


@app.get("/v1/models", response_model=ModelList)
def list_models() -> ModelList:
    return ModelList(data=[ModelCard(id=m) for m in MODEL_IDS])


def _text(content) -> str:
    return content if isinstance(content, str) else "".join(p.text for p in content)


def _stream(completion_id: str, created: int, model: str, text: str) -> Iterator[str]:
    def frame(delta: dict, finish: str | None = None) -> str:
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
        return f"data: {json.dumps(payload)}\n\n"

    yield frame({"role": "assistant"})
    yield frame({"content": text})
    yield frame({}, "stop")
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
def chat_completions(body: ChatCompletionRequest):
    mode = MODEL_TO_MODE.get(body.model)
    if mode is None:
        return error_response(
            404, f"The model '{body.model}' does not exist.", "invalid_request_error", "model"
        )
    users = [m for m in body.messages if m.role == "user"]
    if not users:
        return error_response(
            400, "A user message is required.", "invalid_request_error", "messages"
        )

    opts = body.rag_options
    try:
        request = QueryRequest(
            question=_text(users[-1].content),
            pattern=opts.pattern if opts and opts.pattern else mode,
            caller_id=get_settings().webui_demo_caller_id,  # server-set, never from the browser
            filters=SemanticFilters(
                act=opts.act, status=opts.status, access_level=opts.access_level
            )
            if opts
            else None,
            limit=opts.limit if opts and opts.limit else 5,
            generate_answer=False,  # server-set
            required_acts=opts.required_acts if opts else [],
            chapter=opts.chapter if opts else None,
        )
    except ValidationError as exc:
        return error_response(400, exc.errors()[0]["msg"], "invalid_request_error", "messages")

    text = run_pattern(request).message
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    if body.stream:
        return StreamingResponse(
            _stream(completion_id, created, body.model, text), media_type="text/event-stream"
        )
    return ChatCompletionResponse(
        id=completion_id,
        created=created,
        model=body.model,
        choices=[ChatChoice(message=ChatResponseMessage(content=text))],
    )
