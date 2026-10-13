"""MongoDB document shapes only. No connection, no provisioning."""

from typing import Any

from pydantic import BaseModel, Field


class ChunkDocument(BaseModel):
    chunk_id: str
    section_id: str
    act: str  # "BNS" or "IPC"
    heading: str | None = None
    text: str
    status: str | None = None
    access_level: str | None = None
    chapter: str | None = None
    source: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None  # voyage-3.5, 1,024 dimensions
    embedding_model: str = "voyage-3.5"
