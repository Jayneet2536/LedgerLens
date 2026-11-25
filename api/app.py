from contextlib import asynccontextmanager
import os

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    ReindexAcceptedResponse,
    ReindexRequest,
    ReindexStatusResponse,
    RetrievalStrategyRequest,
    RetrievalStrategyResponse,
    StrategiesResponse,
)
from api.state import (
    ApiServiceState,
    InvalidStrategyError,
    NoIndexLoadedError,
    ReindexInProgressError,
)


service_state = ApiServiceState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    service_state.initialize()
    app.state.rag = service_state
    yield


app = FastAPI(
    title="RAG Chat API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_service_state(request: Request) -> ApiServiceState:
    return request.app.state.rag


def strategy_error(error: InvalidStrategyError) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "message": str(error),
            "valid_strategies": error.valid_values,
        },
    )


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    state: ApiServiceState = Depends(get_service_state),
) -> ChatResponse:
    try:
        return state.chat(request.message)
    except ReindexInProgressError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except NoIndexLoadedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/health", response_model=HealthResponse)
def health(state: ApiServiceState = Depends(get_service_state)) -> HealthResponse:
    return state.health()


@app.get("/strategies", response_model=StrategiesResponse)
def strategies(state: ApiServiceState = Depends(get_service_state)) -> StrategiesResponse:
    return state.strategies()


@app.post("/strategy/retrieval", response_model=RetrievalStrategyResponse)
def set_retrieval_strategy(
    request: RetrievalStrategyRequest,
    state: ApiServiceState = Depends(get_service_state),
) -> RetrievalStrategyResponse:
    try:
        return state.update_retrieval_strategy(request.retrieval_strategy)
    except InvalidStrategyError as exc:
        raise strategy_error(exc) from exc
    except ReindexInProgressError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except NoIndexLoadedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/reindex", response_model=ReindexAcceptedResponse, status_code=202)
def reindex(
    request: ReindexRequest,
    background_tasks: BackgroundTasks,
    state: ApiServiceState = Depends(get_service_state),
) -> ReindexAcceptedResponse:
    try:
        next_config = state.prepare_reindex_config(
            chunking_strategy=request.chunking_strategy,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
        )
    except InvalidStrategyError as exc:
        raise strategy_error(exc) from exc
    except ReindexInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    background_tasks.add_task(state.run_reindex, next_config)
    return ReindexAcceptedResponse(
        status="reindexing",
        detail="Reindex started. Poll /reindex-status for progress.",
    )


@app.post("/ingest", response_model=ReindexAcceptedResponse, status_code=202)
def ingest(
    background_tasks: BackgroundTasks,
    state: ApiServiceState = Depends(get_service_state),
) -> ReindexAcceptedResponse:
    try:
        next_config = state.prepare_reindex_config(
            chunking_strategy=None,
            chunk_size=None,
            chunk_overlap=None,
        )
    except ReindexInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    background_tasks.add_task(state.run_reindex, next_config)
    return ReindexAcceptedResponse(
        status="reindexing",
        detail="Ingestion started. Poll /reindex-status for progress.",
    )


@app.get("/reindex-status", response_model=ReindexStatusResponse)
def reindex_status(state: ApiServiceState = Depends(get_service_state)) -> ReindexStatusResponse:
    return state.reindex_status()
