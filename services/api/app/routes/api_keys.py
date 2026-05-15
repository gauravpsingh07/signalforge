from fastapi import APIRouter

router = APIRouter(tags=["api-keys"])


@router.get("/api-keys/status")
async def api_keys_status() -> dict[str, str]:
    return {"status": "not_implemented", "phase": "1"}
