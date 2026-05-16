from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_current_user, get_metadata_store
from app.services.metadata_store import MetadataStore, UserRecord
from app.services.pipeline_service import PipelineService

router = APIRouter(tags=["pipeline"])


async def owned_project_ids(
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
) -> set[str]:
    projects = await store.list_projects(current_user.id)
    return {project.id for project in projects}


@router.get("/pipeline-health")
async def pipeline_health(
    project_ids: Annotated[set[str], Depends(owned_project_ids)],
) -> dict:
    return PipelineService().health(project_ids)


@router.get("/worker-health")
async def worker_health(
    project_ids: Annotated[set[str], Depends(owned_project_ids)],
) -> dict:
    return PipelineService().health(project_ids)


@router.get("/pipeline/jobs")
async def list_pipeline_jobs(
    project_ids: Annotated[set[str], Depends(owned_project_ids)],
    status: str | None = None,
    job_type: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: Annotated[int, Query(ge=1, le=250)] = 100,
) -> dict:
    jobs = PipelineService().list_jobs(
        status=status,
        job_type=job_type,
        start=start,
        end=end,
        limit=limit,
        allowed_project_ids=project_ids,
    )
    return {"jobs": jobs}


@router.post("/pipeline/jobs/{job_id}/retry")
async def retry_pipeline_job(
    job_id: str,
    project_ids: Annotated[set[str], Depends(owned_project_ids)],
) -> dict:
    job = PipelineService().retry_job(job_id, project_ids)
    if job is None:
        raise HTTPException(status_code=404, detail="Retryable job not found")
    return {"job": job}
