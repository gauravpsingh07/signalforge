from fastapi import APIRouter

router = APIRouter(prefix="/v1/events", tags=["events"])


@router.get("/status")
async def events_status() -> dict[str, str]:
    return {"status": "not_implemented", "phase": "2"}
