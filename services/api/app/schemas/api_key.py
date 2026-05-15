from pydantic import BaseModel, Field


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    mode: str = Field(default="demo", pattern="^(demo|live)$")


class ApiKeyCreateResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    raw_key: str
    created_at: str


class ApiKeyPublic(BaseModel):
    id: str
    project_id: str
    name: str
    key_prefix: str
    masked_key: str
    created_at: str
    last_used_at: str | None = None
    revoked_at: str | None = None
    is_revoked: bool
