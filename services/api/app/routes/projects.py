from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, get_metadata_store
from app.schemas.project import ProjectCreateRequest, ProjectPublic, ProjectUpdateRequest
from app.services.event_store_service import EventStoreService
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
    limit: int = 100,
) -> dict:
    project = await store.get_project(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    bounded_limit = min(max(limit, 1), 200)
    events = EventStoreService().list_events(
        project_id=project.id,
        service=service,
        level=level,
        environment=environment,
        start=start,
        end=end,
        search=search,
        limit=bounded_limit,
    )
    return {"events": events}


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
