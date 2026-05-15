from datetime import UTC, datetime

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    settings = get_settings()
    return {
        "service": "signalforge-api",
        "status": "healthy",
        "version": settings.version,
        "timestamp": datetime.now(UTC).isoformat(),
    }
