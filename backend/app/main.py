from __future__ import annotations
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, batch, chat, documents, health
from app.config import get_settings

# ──────────────────────────────────────────────
# Logging setup
# ──────────────────────────────────────────────
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Lifespan
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("Enterprise Knowledge Intelligence Platform — Backend")
    logger.info("Ollama:    %s  model=%s", settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL)
    logger.info("Cloud:     %s  (%s)", settings.CLOUD_PROVIDER, settings.CLOUD_MODEL_NAME)
    logger.info("Retrieval: %s", settings.RETRIEVAL_API_URL)
    logger.info("Ingestion: %s", settings.INGESTION_API_URL)
    logger.info("MCP:       %s", settings.MCP_SERVER_URL)
    logger.info("=" * 60)
    yield
    logger.info("Shutting down...")


# ──────────────────────────────────────────────
# App
# ──────────────────────────────────────────────
app = FastAPI(
    title="Enterprise Knowledge Intelligence Platform",
    description=(
        "RAG-powered enterprise assistant. Answers questions from uploaded documents, "
        "cites exact sections, and says when the corpus does not contain the answer."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow frontend on localhost:5173, localhost:3000, or any dev port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix="/api", tags=["Auth & RBAC"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])
app.include_router(batch.router, prefix="/api", tags=["Batch"])
app.include_router(health.router, prefix="/api", tags=["Health"])


# ──────────────────────────────────────────────
# Global error handler
# ──────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s %s — %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.LOG_LEVEL.lower(),
    )
