"""Local memory API; final Answer and Judge belong to the calling platform."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from adaptive_evidence.core import Config, ConflictError, MemoryStore
from . import __version__
from .planner import BoundedSearch
from .runtime import LocalPlanner


class Message(BaseModel):
    role: str = Field(min_length=1)
    content: str = Field(min_length=1)
    timestamp: int | None = Field(default=None, strict=True)


class Add(BaseModel):
    request_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    messages: list[Message] = Field(min_length=1)


class Search(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    options: list[str] | None = None
    top_k: int = Field(ge=1, le=100, strict=True)


def authenticate(authorization: str | None = Header(default=None),
                 x_api_key: str | None = Header(default=None)):
    expected = os.getenv("MEMORY_API_KEY", "")
    if not expected and os.getenv("GAPTRAIL_LOCAL_NO_AUTH") == "1":
        return
    if not expected:
        raise HTTPException(503, "Configure the memory service key")
    provided = x_api_key or ""
    if not provided and authorization:
        scheme, _, credential = authorization.partition(" ")
        if scheme.lower() in {"bearer", "token"}:
            provided = credential
    if not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(401, "Invalid service key")


class Engine:
    def __init__(self, store, tokenizer, runtime_factory, metrics_path):
        self.store, self.tokenizer = store, tokenizer
        self.runtime_factory = runtime_factory
        self.metrics_path = Path(metrics_path)
        self.lock = threading.RLock()

    def search(self, payload):
        with self.lock:
            runtime = self.runtime_factory()
            planner = BoundedSearch(self.store, runtime, self.tokenizer)
            started = time.monotonic()
            error = None
            try:
                return planner.search(**payload, mode="query_document_evidence")
            except Exception as exc:
                error = type(exc).__name__
                raise
            finally:
                trace = planner.last_trace or {}
                record = dict(request_id=uuid4().hex,
                    at_utc=datetime.now(timezone.utc).isoformat(),
                    query_sha256=hashlib.sha256(payload["query"].encode()).hexdigest(),
                    status="error" if error else "ok", error_type=error,
                    query_count=trace.get("query_count"), extra_queries=trace.get("extra_queries"),
                    planner_calls=trace.get("planner_calls"),
                    stop_reason=trace.get("stop_reason", "local_request_error"),
                    search_seconds=time.monotonic()-started,
                    planner_prompt_tokens=trace.get("prompt_tokens"),
                    planner_completion_tokens=trace.get("completion_tokens"),
                    metered_planner_seconds=sum(c["seconds"] for c in getattr(runtime, "calls", [])),
                    paid_api_cost_usd=0, failed_request_token_usage_unknown=bool(error))
                self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
                with self.metrics_path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(record, ensure_ascii=False)+"\n")
                runtime.close()


def load_engine():
    from adaptive_evidence.encoder import BGEEncoder
    from transformers import AutoTokenizer
    if not os.getenv("MEMORY_API_KEY") and os.getenv("GAPTRAIL_LOCAL_NO_AUTH") != "1":
        raise RuntimeError("Set MEMORY_API_KEY or explicitly enable local no-auth mode")
    encoder = BGEEncoder(os.environ["GAPTRAIL_BGE_PATH"], device="cpu")
    tokenizer = AutoTokenizer.from_pretrained(os.environ["GAPTRAIL_TOKENIZER_PATH"],
        local_files_only=True, trust_remote_code=False)
    store = MemoryStore(os.getenv("GAPTRAIL_DATABASE", "data/memory.sqlite3"),
        encoder, Config(context_chars=24000))
    return Engine(store, tokenizer, lambda: LocalPlanner(tokenizer,
        os.getenv("GAPTRAIL_PLANNER_URL", "http://127.0.0.1:18405/v1/chat/completions"),
        os.getenv("GAPTRAIL_MODEL_ALIAS", "gaptrail-qwen")),
        os.getenv("GAPTRAIL_METRICS", "data/search-metrics.jsonl"))


def create_app(engine_factory=load_engine):
    @asynccontextmanager
    async def lifespan(app):
        app.state.engine = engine_factory()
        try:
            yield
        finally:
            encoder = app.state.engine.store.encoder
            if hasattr(encoder, "close"):
                encoder.close()
            app.state.engine.store.cache.clear()

    app = FastAPI(title="GapTrail Memory", version=__version__, lifespan=lifespan)

    def engine():
        return app.state.engine

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse(status_code=422, content={"detail": "Invalid request schema"})

    @app.get("/health")
    def health():
        return dict(status="ok", name="GapTrail Memory", version=__version__,
            search_planner="bounded-missing-relations-v2", max_extra_queries=2,
            max_planner_calls=3, evidence="original_source_spans",
            answer_owner="external_platform", judge_owner="external_platform")

    @app.post("/add", dependencies=[Depends(authenticate)])
    def add(payload: Add, service=Depends(engine)):
        try:
            with service.lock:
                service.store.add(**payload.model_dump())
        except ConflictError:
            raise HTTPException(409, "Request ID conflicts with an existing write")
        except (ValueError, OverflowError, OSError):
            raise HTTPException(422, "Invalid memory data")
        return dict(success=True, request_id=payload.request_id,
                    user_id=payload.user_id, session_id=payload.session_id)

    @app.post("/search", dependencies=[Depends(authenticate)])
    def search(payload: Search, service=Depends(engine)):
        try:
            return {"data": service.search(payload.model_dump())}
        except Exception:
            raise HTTPException(502, "Local retrieval or planner request failed; inspect local metrics")

    return app


app = create_app()
