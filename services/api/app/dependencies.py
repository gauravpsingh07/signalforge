from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.services.metadata_store import (
    InMemoryMetadataStore,
    MetadataStore,
    PostgresMetadataStore,
    UserRecord,
)
from app.utils.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)
_local_store = InMemoryMetadataStore()
_postgres_store = PostgresMetadataStore()


def get_metadata_store() -> MetadataStore:
    if get_settings().database_url:
        return _postgres_store
    return _local_store


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
