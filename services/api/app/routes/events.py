from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import get_settings
from app.dependencies import get_ingestion_api_key, get_metadata_store, get_rate_limiter
from app.schemas.event import (
    BatchEventAcceptedResponse,
    BatchEventIngestRequest,
    EventAcceptedResponse,
    EventIngestRequest,
)
from app.services.metadata_store import ApiKeyRecord, MetadataStore
from app.services.queue_service import QueueService
from app.services.rate_limit_service import InMemoryRateLimiter

router = APIRouter(prefix="/v1/events", tags=["events"])


@router.get("/status")
async def events_status() -> dict[str, str]:
    return {"status": "implemented", "phase": "2"}


@router.post("", response_model=EventAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(
    payload: EventIngestRequest,
    request: Request,
    api_key: Annotated[ApiKeyRecord, Depends(get_ingestion_api_key)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
    rate_limiter: Annotated[InMemoryRateLimiter, Depends(get_rate_limiter)],
) -> EventAcceptedResponse:
    await _enforce_rate_limit(request, api_key, rate_limiter)

    job = await QueueService(store).enqueue_event(api_key, payload)
    await store.mark_api_key_used(api_key.id)
    return EventAcceptedResponse(eventId=payload.eventId or job.id, jobId=job.id)


@router.post("/batch", response_model=BatchEventAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_event_batch(
    payload: BatchEventIngestRequest,
    request: Request,
    api_key: Annotated[ApiKeyRecord, Depends(get_ingestion_api_key)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
    rate_limiter: Annotated[InMemoryRateLimiter, Depends(get_rate_limiter)],
) -> BatchEventAcceptedResponse:
    await _enforce_rate_limit(request, api_key, rate_limiter, cost=len(payload.events))

    jobs = await QueueService(store).enqueue_batch(api_key, payload.events)
    await store.mark_api_key_used(api_key.id)
    return BatchEventAcceptedResponse(
        acceptedCount=len(jobs),
        jobIds=[job.id for job in jobs],
    )


async def _enforce_rate_limit(
    request: Request,
    api_key: ApiKeyRecord,
    rate_limiter: InMemoryRateLimiter,
    cost: int = 1,
) -> None:
    settings = get_settings()
    for _ in range(cost):
        key_result = await rate_limiter.check(
            f"api-key:{api_key.id}",
            settings.ingest_rate_limit_per_minute,
        )
        if not key_result.allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Retry after {key_result.retry_after_seconds} seconds.",
                headers={"Retry-After": str(key_result.retry_after_seconds)},
            )

        client_host = request.client.host if request.client else "unknown"
        ip_result = await rate_limiter.check(
            f"ip:{client_host}",
            settings.ingest_rate_limit_per_ip_minute,
        )
        if not ip_result.allowed:
            raise HTTPException(
                status_code=429,
                detail=f"IP rate limit exceeded. Retry after {ip_result.retry_after_seconds} seconds.",
                headers={"Retry-After": str(ip_result.retry_after_seconds)},
            )
