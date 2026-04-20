"""
DocAssist+ & VoiceBot — Production FastAPI Application
=======================================================
Author: AI Engineer
Version: 1.0.0
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import time
import logging
import uuid

from backend.routers import documents, query, chat, voice, health
from backend.config.settings import settings
from backend.utils.logger import setup_logger

# ── Logger ──────────────────────────────────────────────────────────────────
logger = setup_logger(__name__)

# ── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="DocAssist+ & VoiceBot API",
    description="Production-grade RAG + Intent/Emotion Detection + Multi-turn VoiceBot",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── Middleware ───────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # tighten later
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def add_request_id_and_timing(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
    logger.info(
        f"[{request_id}] {request.method} {request.url.path} "
        f"→ {response.status_code} ({duration_ms:.1f}ms)"
    )
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again.",
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
    )


# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(health.router, tags=["Health"])
app.include_router(documents.router, prefix="/documents", tags=["Documents"])
app.include_router(query.router, prefix="/query", tags=["Query"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(voice.router, prefix="/voice", tags=["Voice"])


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 DocAssist+ API starting up...")
    logger.info(f"   Environment : {settings.ENVIRONMENT}")
    logger.info(f"   LLM Model   : {settings.LLM_MODEL}")
    logger.info(f"   Embed Model : {settings.EMBEDDING_MODEL}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("👋 DocAssist+ API shutting down...")