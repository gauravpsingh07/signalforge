from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, get_metadata_store
from app.schemas.api_key import ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyPublic
from app.services.metadata_store import ApiKeyRecord, MetadataStore, UserRecord
from app.utils.security import api_key_prefix, generate_api_key, hash_api_key

router = APIRouter(tags=["api-keys"])


@router.get("/api-keys/status")
async def api_keys_status() -> dict[str, str]:
    return {"status": "implemented", "phase": "1"}


@router.post(
    "/projects/{project_id}/api-keys",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_api_key(
    project_id: str,
    payload: ApiKeyCreateRequest,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
) -> ApiKeyCreateResponse:
    project = await store.get_project(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    raw_key = generate_api_key(payload.mode)
    key = await store.create_api_key(
        project_id=project.id,
        name=payload.name,
        key_hash=hash_api_key(raw_key),
        key_prefix=api_key_prefix(raw_key),
    )

    return ApiKeyCreateResponse(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        raw_key=raw_key,
        created_at=key.created_at,
    )


@router.get("/projects/{project_id}/api-keys", response_model=list[ApiKeyPublic])
async def list_project_api_keys(
    project_id: str,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
) -> list[ApiKeyPublic]:
    project = await store.get_project(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    keys = await store.list_api_keys(project.id)
    return [_api_key_public(key) for key in keys]


@router.delete("/api-keys/{key_id}", response_model=ApiKeyPublic)
async def revoke_api_key(
    key_id: str,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
) -> ApiKeyPublic:
    key = await store.get_api_key(key_id)
    if key is None:
        raise HTTPException(status_code=404, detail="API key not found")

    project = await store.get_project(key.project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="API key not found")

    revoked = await store.revoke_api_key(key.id)
    if revoked is None:
        raise HTTPException(status_code=404, detail="API key not found")
    return _api_key_public(revoked)


def _api_key_public(key: ApiKeyRecord) -> ApiKeyPublic:
    data = asdict(key)
    data.pop("key_hash")
    data["masked_key"] = f"{key.key_prefix}..."
    data["is_revoked"] = key.is_revoked
    return ApiKeyPublic(**data)
