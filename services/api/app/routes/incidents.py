from fastapi import APIRouter

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("/status")
async def incidents_status() -> dict[str, str]:
    return {"status": "not_implemented", "phase": "6"}
