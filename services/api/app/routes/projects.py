from fastapi import APIRouter

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/status")
async def projects_status() -> dict[str, str]:
    return {"status": "not_implemented", "phase": "1"}
