from hmac import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.services.metadata_store import (
    ApiKeyRecord,
    InMemoryMetadataStore,
    MetadataStore,
    PostgresMetadataStore,
    UserRecord,
)
from app.services.rate_limit_service import InMemoryRateLimiter
from app.utils.security import api_key_prefix, decode_access_token, hash_api_key

bearer_scheme = HTTPBearer(auto_error=False)
_local_store = InMemoryMetadataStore()
_postgres_store = PostgresMetadataStore()
_rate_limiter = InMemoryRateLimiter()


def get_metadata_store() -> MetadataStore:
    if get_settings().database_url:
        return _postgres_store
    return _local_store


def get_rate_limiter() -> InMemoryRateLimiter:
    return _rate_limiter


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
) -> UserRecord:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await store.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user


async def get_ingestion_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
) -> ApiKeyRecord:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing ingestion API key")

    raw_key = credentials.credentials
    key = await store.get_api_key_by_prefix(api_key_prefix(raw_key))
    if key is None or key.is_revoked:
        raise HTTPException(status_code=401, detail="Invalid ingestion API key")

    if not compare_digest(key.key_hash, hash_api_key(raw_key)):
        raise HTTPException(status_code=401, detail="Invalid ingestion API key")

    return key
