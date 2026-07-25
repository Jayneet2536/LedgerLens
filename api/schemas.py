from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class Source(BaseModel):
    content: str
    metadata: dict[str, Any]


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    latency_ms: float


class HealthResponse(BaseModel):
    chroma_reachable: bool
    index_loaded: bool
    reindex_status: Literal["idle", "reindexing", "error"]
    chunking_strategy: str
    retrieval_strategy: str
    top_k_results: int
    detail: str | None = None


class StrategiesResponse(BaseModel):
    chunking_strategies: list[str]
    retrieval_strategies: list[str]


class RetrievalStrategyRequest(BaseModel):
    retrieval_strategy: str


class RetrievalStrategyResponse(BaseModel):
    retrieval_strategy: str
    top_k_results: int


class ReindexRequest(BaseModel):
    chunking_strategy: str | None = None
    chunk_size: int | None = Field(default=None, gt=0)
    chunk_overlap: int | None = Field(default=None, ge=0)


class ReindexAcceptedResponse(BaseModel):
    status: Literal["reindexing"]
    detail: str


class ReindexStatusResponse(BaseModel):
    status: Literal["idle", "reindexing", "error"]
    detail: str | None = None
