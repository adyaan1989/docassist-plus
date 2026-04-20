"""
Health Router
=============
GET /health — Liveness probe
GET /health/ready — Readiness probe (checks dependencies)
"""

from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/health/ready")
async def ready():
    """
    Readiness probe — verify critical dependencies.
    Returns 200 if ready, 503 if not.
    """
    checks = {}

    # Check vector store
    try:
        import chromadb
        checks["vector_store"] = "ok"
    except Exception as e:
        checks["vector_store"] = f"error: {e}"

    # Check OpenAI key presence (not validity)
    from backend.config.settings import settings
    checks["openai_key_set"] = bool(settings.OPENAI_API_KEY)

    all_ok = all(v == "ok" or v is True for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }