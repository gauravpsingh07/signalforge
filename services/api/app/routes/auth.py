from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, get_metadata_store
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserPublic
from app.services.metadata_store import DuplicateEmailError, MetadataStore, UserRecord
from app.utils.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status")
async def auth_status() -> dict[str, str]:
    return {"status": "implemented", "phase": "1"}


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
) -> AuthResponse:
    try:
        user = await store.create_user(
            email=payload.email,
            password_hash=hash_password(payload.password),
        )
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=409, detail="Email is already registered") from exc

    return AuthResponse(
        access_token=create_access_token(user.id),
        user=_user_public(user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    store: Annotated[MetadataStore, Depends(get_metadata_store)],
) -> AuthResponse:
    user = await store.get_user_by_email(payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return AuthResponse(
        access_token=create_access_token(user.id),
        user=_user_public(user),
    )


@router.get("/me", response_model=UserPublic)
async def me(current_user: Annotated[UserRecord, Depends(get_current_user)]) -> UserPublic:
    return _user_public(current_user)


def _user_public(user: UserRecord) -> UserPublic:
    return UserPublic(**{key: value for key, value in asdict(user).items() if key != "password_hash"})
