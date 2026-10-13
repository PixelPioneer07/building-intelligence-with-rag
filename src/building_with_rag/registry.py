"""The one shared registry of course modes and OpenAI-style model IDs."""

REGISTRY: dict[str, str] = {
    "semantic": "rag-semantic",
    "hybrid": "rag-hybrid",
    "hybrid-reranked": "rag-hybrid-reranked",
    "structured": "rag-structured",
    "decomposition": "rag-decomposition",
    "hyde": "rag-hyde",
}

MODEL_TO_MODE: dict[str, str] = {model: mode for mode, model in REGISTRY.items()}
MODES = tuple(REGISTRY)
MODEL_IDS = tuple(REGISTRY.values())
