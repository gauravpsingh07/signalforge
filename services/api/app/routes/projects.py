from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user, get_metadata_store
from app.schemas.project import ProjectCreateRequest, ProjectPublic, ProjectUpdateRequest
from app.services.alert_service import AlertService
from app.services.anomaly_service import AnomalyQueryService
from app.services.event_store_service import EventStoreService
from app.services.incident_service import IncidentQueryService
from app.services.metrics_service import MetricsService
from app.services.metadata_store import (
    DuplicateProjectSlugError,
    MetadataStore,
    ProjectRecord,
    UserRecord,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/status")
async def projects_status() -> dict[str, str]:
    return {"status": "implemented", "phase": "1"}


@router.get("", response_model=list[ProjectPublic])
async def list_projects(
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
) -> list[ProjectPublic]:
    projects = await store.list_projects(current_user.id)
    return [_project_public(project) for project in projects]


@router.post("", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
) -> ProjectPublic:
    try:
        project = await store.create_project(
            user_id=current_user.id,
            name=payload.name,
            description=payload.description,
            environment_default=payload.environment_default,
        )
    except DuplicateProjectSlugError as exc:
        raise HTTPException(status_code=409, detail="Project slug already exists") from exc

    return _project_public(project)


@router.get("/{project_id}/events")
async def list_project_events(
    project_id: str,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
    service: str | None = None,
    level: str | None = None,
    environment: str | None = None,
    start: str | None = None,
    end: str | None = None,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict:
    project = await store.get_project(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    events = EventStoreService().list_events(
        project_id=project.id,
        service=service,
        level=level,
        environment=environment,
        start=start,
        end=end,
        search=search,
        limit=limit,
    )
    return {"events": events}


@router.get("/{project_id}/metrics")
async def get_project_metrics(
    project_id: str,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
    range: str = "1h",
    service: str | None = None,
    environment: str | None = None,
    bucketSize: int = 60,
) -> dict:
    project = await store.get_project(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return MetricsService().get_project_metrics(
        project_id=project.id,
        range_value=range,
        service=service,
        environment=environment,
        bucket_size=bucketSize,
    )


@router.get("/{project_id}/services")
async def get_project_services(
    project_id: str,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
) -> dict:
    project = await store.get_project(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    metrics = MetricsService().get_project_metrics(project_id=project.id)
    return {"services": metrics["services"]}


@router.get("/{project_id}/anomalies")
async def list_project_anomalies(
    project_id: str,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
    service: str | None = None,
    environment: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    anomaly_type: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict:
    project = await store.get_project(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    anomalies = AnomalyQueryService().list_anomalies(
        project_id=project.id,
        service=service,
        environment=environment,
        severity=severity,
        status=status,
        anomaly_type=anomaly_type,
        start=start,
        end=end,
        limit=limit,
    )
    return {"anomalies": anomalies}


@router.get("/{project_id}/incidents")
async def list_project_incidents(
    project_id: str,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
    status: str | None = None,
    severity: str | None = None,
    service: str | None = None,
    environment: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict:
    project = await store.get_project(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    incidents = IncidentQueryService().list_incidents(
        project_id=project.id,
        status=status,
        severity=severity,
        service=service,
        environment=environment,
        limit=limit,
    )
    return {"incidents": incidents}


@router.get("/{project_id}/alerts")
async def list_project_alerts(
    project_id: str,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
    incident_id: str | None = None,
    status: str | None = None,
    channel: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict:
    project = await store.get_project(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    alert_service = AlertService()
    return {
        "alerts": alert_service.list_alerts(
            project_id=project.id,
            incident_id=incident_id,
            status=status,
            channel=channel,
            limit=limit,
        ),
        "discordConfigured": alert_service.discord_configured(),
    }


@router.get("/{project_id}", response_model=ProjectPublic)
async def get_project(
    project_id: str,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
) -> ProjectPublic:
    project = await store.get_project(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_public(project)


@router.patch("/{project_id}", response_model=ProjectPublic)
async def update_project(
    project_id: str,
    payload: ProjectUpdateRequest,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
) -> ProjectPublic:
    project = await store.update_project(
        project_id=project_id,
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        environment_default=payload.environment_default,
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_public(project)


def _project_public(project: ProjectRecord) -> ProjectPublic:
    return ProjectPublic(**asdict(project))
