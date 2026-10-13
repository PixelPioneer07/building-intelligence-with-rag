"""Typed contracts. No behavior. Later stories extend these additively; names never change."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Must match building_with_rag.registry.MODES.
Pattern = Literal["semantic", "hybrid", "hybrid-reranked", "structured", "decomposition", "hyde"]


class SemanticFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    act: list[str] = Field(default_factory=list)
    status: list[str] = Field(default_factory=list)
    access_level: list[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    pattern: Pattern
    caller_id: str | None = None
    filters: SemanticFilters | None = None
    limit: int = Field(default=5, ge=1, le=20)
    generate_answer: bool = False
    required_acts: list[str] = Field(default_factory=list)
    chapter: str | None = None


class RetrievedChunk(BaseModel):
    chunk_id: str
    section_id: str
    act: str
    text: str
    heading: str | None = None
    score: float | None = None
    source: dict[str, Any] = Field(default_factory=dict)  # source fields; origin preserved


class GenerationResult(BaseModel):
    outcome: Literal["answered", "insufficient_evidence", "unavailable", "malformed"]
    answer: str | None = None
    claims: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    supporting_passages: list[RetrievedChunk] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    trace: dict[str, Any] = Field(default_factory=dict)
    context_outcome: str | None = None
    confidence: float | str | None = None
    draft_answer: str | None = None
    issues: list[str] = Field(default_factory=list)
    attempts: int = 0
    low_confidence_reason: str | None = None


class SubquestionEvidence(BaseModel):
    subquestion: str
    status: Literal["evidenced", "no_evidence"]
    results: list[RetrievedChunk] = Field(default_factory=list)
    reason: str | None = None


class OmittedCandidate(BaseModel):
    chunk_id: str
    omitted_reason: str


class StructuredSignals(BaseModel):
    intent: Literal["exact_lookup", "filter", "aggregation"]
    act: str | None = None
    section_number: str | None = None
    chapter: str | None = None


class QueryResult(BaseModel):
    pattern: str
    status: str
    message: str
    trace: dict[str, Any] = Field(default_factory=dict)
    results: list[RetrievedChunk] = Field(default_factory=list)
    generation: GenerationResult | None = None
    omitted_candidates: list[OmittedCandidate] = Field(default_factory=list)
    subquestions: list[SubquestionEvidence] = Field(default_factory=list)
    hyde_direct_candidates: list[RetrievedChunk] = Field(default_factory=list)
    hyde_query_candidates: list[RetrievedChunk] = Field(default_factory=list)
    hyde_hypothetical_text_debug: str | None = None


# ---- OpenAI-compatible adapter ----


class RagOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern: Pattern | None = None
    act: list[str] = Field(default_factory=list)
    status: list[str] = Field(default_factory=list)
    access_level: list[str] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1, le=20)
    required_acts: list[str] = Field(default_factory=list)
    chapter: str | None = None


class ChatTextPart(BaseModel):
    type: Literal["text"]
    text: str


class ChatMessage(BaseModel):
    role: Literal["system", "developer", "user", "assistant"]
    content: str | list[ChatTextPart]


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")  # tolerate the usual OpenAI client extras

    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    n: int = Field(default=1, ge=1, le=1)
    rag_options: RagOptions | None = None


class ModelCard(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "building-with-rag"


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelCard]


class ChatResponseMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatResponseMessage
    finish_reason: str = "stop"


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoice]
    usage: Usage = Field(default_factory=Usage)


class ErrorBody(BaseModel):
    message: str
    type: str
    param: str | None = None
    code: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody
