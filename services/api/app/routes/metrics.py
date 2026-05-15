from fastapi import APIRouter

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/status")
async def metrics_status() -> dict[str, str]:
    return {"status": "implemented", "phase": "4"}
