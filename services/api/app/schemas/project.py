from pydantic import BaseModel, Field


class ProjectPublic(BaseModel):
    id: str
    user_id: str
    name: str
    slug: str
    description: str | None = None
    environment_default: str
    created_at: str
    updated_at: str


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    environment_default: str = Field(default="production", min_length=2, max_length=40)


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    environment_default: str | None = Field(default=None, min_length=2, max_length=40)
