import copy
import re
import threading
import time
from typing import Any

import chromadb
from langchain_core.documents import Document
from langchain_groq import ChatGroq

from config import CONFIG
from embeddings.models import EmbeddingFactory
from main import run_ingestion
from retrieval.strategies import RetrieverFactory
from vectorstore.databases import VectorStoreFactory

from api.context import build_capped_context
from api.schemas import (
    ChatResponse,
    HealthResponse,
    ReindexStatusResponse,
    RetrievalStrategyResponse,
    Source,
    StrategiesResponse,
)
from api.strategies import get_chunking_strategies, get_retrieval_strategies


class NoIndexLoadedError(RuntimeError):
    pass


class ReindexInProgressError(RuntimeError):
    pass


class InvalidStrategyError(ValueError):
    def __init__(self, strategy_type: str, value: str, valid_values: list[str]):
        super().__init__(f"Unknown {strategy_type} strategy: {value}")
        self.strategy_type = strategy_type
        self.value = value
        self.valid_values = valid_values


class ApiServiceState:
    def __init__(self, base_config: dict[str, Any] | None = None):
        self.config = copy.deepcopy(base_config or CONFIG)
        self.chunking_strategies = get_chunking_strategies()
        self.retrieval_strategies = get_retrieval_strategies()
        self.embedding_model = None
        self.vector_db = None
        self.documents: list[Document] = []
        self.retriever = None
        self.llm = None
        self.index_loaded = False
        self.status = "idle"
        self.status_detail: str | None = None
        self._lock = threading.RLock()
        self._collection_lock = threading.Lock()

    def initialize(self) -> None:
        self._validate_required_keys()
        embedding_model = EmbeddingFactory.get_embedding_model(self.config)
        llm = ChatGroq(
            api_key=self.config["groq_api_key"],
            model=self.config.get("groq_model", "openai/gpt-oss-120b"),
            temperature=0.0,
        )

        vector_db = None
        documents: list[Document] = []
        retriever = None
        detail = None
        auto_bootstrap = False

        try:
            vector_db, documents, retriever = self._load_index_and_retriever(
                embedding_model,
                self.config,
            )
            if not documents:
                detail = "No index found — automatically building index from default configuration."
                auto_bootstrap = True
        except Exception as exc:
            detail = f"No index loaded: {exc}"

        with self._lock:
            self.embedding_model = embedding_model
            self.llm = llm
            self.vector_db = vector_db
            self.documents = documents
            self.retriever = retriever
            self.index_loaded = retriever is not None
            self.status_detail = detail

        if auto_bootstrap:
            # Note: This in-memory state is per-process. If run with multiple uvicorn workers,
            # each worker gets its own ApiServiceState and would race against the others here.
            try:
                next_config = self.prepare_reindex_config(
                    chunking_strategy=None, chunk_size=None, chunk_overlap=None
                )
                with self._lock:
                    self.status_detail = "No index found — automatically building index from default configuration."
                threading.Thread(target=self.run_reindex, args=(next_config,), daemon=True).start()
            except ReindexInProgressError:
                pass

    def health(self) -> HealthResponse:
        with self._lock:
            config = copy.deepcopy(self.config)
            index_loaded = self.index_loaded
            status = self.status
            detail = self.status_detail

        return HealthResponse(
            chroma_reachable=self._is_chroma_reachable(config),
            index_loaded=index_loaded,
            reindex_status=status,
            chunking_strategy=config["chunking_strategy"],
            retrieval_strategy=config["retrieval_strategy"],
            top_k_results=config["top_k_results"],
            detail=detail,
        )

    def strategies(self) -> StrategiesResponse:
        return StrategiesResponse(
            chunking_strategies=self.chunking_strategies,
            retrieval_strategies=self.retrieval_strategies,
        )

    def chat(self, message: str) -> ChatResponse:
        with self._lock:
            if self.status == "reindexing":
                raise ReindexInProgressError("Service is reindexing. Try again after /reindex-status is idle.")
            if not self.index_loaded or self.retriever is None or self.llm is None:
                raise NoIndexLoadedError("No index is loaded. Trigger /ingest first, then retry /chat.")
            retriever = self.retriever
            llm = self.llm

        started_at = time.perf_counter()
        with self._collection_lock:
            retrieved_documents = retriever.invoke(message)
        context, used_documents = build_capped_context(retrieved_documents)
        prompt = self._build_prompt(context, message)
        llm_response = llm.invoke(prompt)
        raw_answer = getattr(llm_response, "content", str(llm_response))
        answer = self._strip_thinking(raw_answer)
        latency_ms = (time.perf_counter() - started_at) * 1000

        return ChatResponse(
            answer=answer,
            sources=[
                Source(content=document.page_content, metadata=document.metadata or {})
                for document in used_documents
            ],
            latency_ms=latency_ms,
        )

    def update_retrieval_strategy(self, retrieval_strategy: str) -> RetrievalStrategyResponse:
        if retrieval_strategy not in self.retrieval_strategies:
            raise InvalidStrategyError("retrieval", retrieval_strategy, self.retrieval_strategies)

        with self._lock:
            if self.status == "reindexing":
                raise ReindexInProgressError("Service is reindexing. Try again after /reindex-status is idle.")
            if not self.index_loaded or self.vector_db is None:
                raise NoIndexLoadedError("No index is loaded. Trigger /ingest first before changing retrieval.")
            next_config = copy.deepcopy(self.config)
            next_config["retrieval_strategy"] = retrieval_strategy
            retriever = RetrieverFactory.get_retriever(
                self.vector_db,
                list(self.documents),
                next_config,
            )
            self.config = next_config
            self.retriever = retriever

        return RetrievalStrategyResponse(
            retrieval_strategy=retrieval_strategy,
            top_k_results=next_config["top_k_results"],
        )

    def prepare_reindex_config(
        self,
        chunking_strategy: str | None,
        chunk_size: int | None,
        chunk_overlap: int | None,
    ) -> dict[str, Any]:
        if chunking_strategy is not None and chunking_strategy not in self.chunking_strategies:
            raise InvalidStrategyError("chunking", chunking_strategy, self.chunking_strategies)

        with self._lock:
            if self.status == "reindexing":
                raise ReindexInProgressError("A reindex is already in progress.")

            next_config = copy.deepcopy(self.config)
            if chunking_strategy is not None:
                next_config["chunking_strategy"] = chunking_strategy
            if chunk_size is not None:
                next_config["chunk_size"] = chunk_size
            if chunk_overlap is not None:
                next_config["chunk_overlap"] = chunk_overlap

            self.status = "reindexing"
            self.status_detail = "Reindex started."

        return next_config

    def run_reindex(self, next_config: dict[str, Any]) -> None:
        try:
            with self._collection_lock:
                run_ingestion(config=next_config)
                vector_db, documents, retriever = self._load_index_and_retriever(
                    self.embedding_model,
                    next_config,
                )
            if retriever is None:
                raise RuntimeError("Reindex completed, but no indexed documents were found.")

            with self._lock:
                self.config = next_config
                self.vector_db = vector_db
                self.documents = documents
                self.retriever = retriever
                self.index_loaded = True
                self.status = "idle"
                self.status_detail = None
        except Exception as exc:
            with self._lock:
                self.status = "error"
                self.status_detail = str(exc)

    def reindex_status(self) -> ReindexStatusResponse:
        with self._lock:
            return ReindexStatusResponse(status=self.status, detail=self.status_detail)

    def _load_index_and_retriever(self, embedding_model, config: dict[str, Any]):
        vector_db = VectorStoreFactory.get_existing_index(embedding_model, config)
        documents = self._load_documents(vector_db)
        if not documents:
            return vector_db, documents, None
        retriever = RetrieverFactory.get_retriever(vector_db, documents, config)
        return vector_db, documents, retriever

    def _load_documents(self, vector_db) -> list[Document]:
        chroma_data = vector_db.get()
        raw_documents = chroma_data.get("documents") or []
        metadatas = chroma_data.get("metadatas") or []
        return [
            Document(page_content=text, metadata=metadata or {})
            for text, metadata in zip(raw_documents, metadatas)
            if text
        ]

    def _is_chroma_reachable(self, config: dict[str, Any]) -> bool:
        try:
            client = chromadb.HttpClient(
                host=config["chroma_host"],
                port=config["chroma_port"],
            )
            client.heartbeat()
            return True
        except Exception:
            return False

    def _validate_required_keys(self) -> None:
        required_keys = ("voyage_api_key", "groq_api_key")
        missing_keys = [
            key
            for key in required_keys
            if not self.config.get(key) or str(self.config[key]).startswith("your-")
        ]
        if missing_keys:
            names = ", ".join(missing_keys)
            raise RuntimeError(f"Missing required API key(s): {names}. Add them to your .env before starting the API.")

    def _build_prompt(self, context: str, question: str) -> str:
        return (
            "You are a senior financial analyst. Answer the question based ONLY on the following context.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}\n"
            "Answer:"
        )

    def _strip_thinking(self, text: str) -> str:
        return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
