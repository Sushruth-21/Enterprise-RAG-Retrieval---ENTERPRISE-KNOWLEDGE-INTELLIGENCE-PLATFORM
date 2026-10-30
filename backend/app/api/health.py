from __future__ import annotations
import time
from fastapi import APIRouter
from app.llm.ollama_client import OllamaClient
from app.llm.cloud_client import get_cloud_client
from app.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="System health check")
async def health_check() -> HealthResponse:
    """Check availability of all backend services and return latency."""
    t0 = time.perf_counter()
    ollama = OllamaClient()
    cloud = get_cloud_client()

    ollama_ok = await ollama.is_available()
    cloud_ok = await cloud.is_available()

    # Mark db_connected=True if retrieval service is reachable
    from app.retrieval.client import RetrievalClient
    retrieval = RetrievalClient()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as client:
            from app.config import get_settings
            resp = await client.get(f"{get_settings().RETRIEVAL_API_URL}/health")
            db_ok = resp.status_code == 200
    except Exception:
        db_ok = False

    overall = "ok" if (ollama_ok or cloud_ok) else "degraded"
    latency_ms = max(1, int((time.perf_counter() - t0) * 1000))

    return HealthResponse(
        status=overall,
        latency_ms=latency_ms,
        version="1.0.0",
        ollama_available=ollama_ok,
        cloud_available=cloud_ok,
        db_connected=db_ok,
    )
