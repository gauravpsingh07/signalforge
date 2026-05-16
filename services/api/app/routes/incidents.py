from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user, get_metadata_store
from app.services.incident_service import IncidentQueryService
from app.services.metadata_store import MetadataStore, UserRecord

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("/status")
async def incidents_status() -> dict[str, str]:
    return {"status": "implemented", "phase": "6"}


@router.get("/{incident_id}")
async def get_incident(
    incident_id: str,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
) -> dict:
    detail = IncidentQueryService().get_incident_detail(incident_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    project = await store.get_project(detail["incident"]["project_id"], current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return detail


@router.post("/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
) -> dict:
    service = IncidentQueryService()
    detail = service.get_incident_detail(incident_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    project = await store.get_project(detail["incident"]["project_id"], current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"incident": service.resolve_incident(incident_id)}
