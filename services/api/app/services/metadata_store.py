from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.database import get_pool
from app.utils.security import slugify


class DuplicateEmailError(Exception):
    pass


class DuplicateProjectSlugError(Exception):
    pass


@dataclass(frozen=True)
class UserRecord:
    id: str
    email: str
    password_hash: str
    created_at: str


@dataclass(frozen=True)
class ProjectRecord:
    id: str
    user_id: str
    name: str
    slug: str
    description: str | None
    environment_default: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ApiKeyRecord:
    id: str
    project_id: str
    name: str
    key_hash: str
    key_prefix: str
    created_at: str
    last_used_at: str | None
    revoked_at: str | None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None


@dataclass(frozen=True)
class WorkerJobRecord:
    id: str
    job_type: str
    entity_id: str | None
    status: str
    attempts: int
    max_attempts: int
    error_message: str | None
    payload: dict | None
    created_at: str
    started_at: str | None
    completed_at: str | None


class MetadataStore(Protocol):
    async def create_user(self, email: str, password_hash: str) -> UserRecord: ...
    async def get_user_by_email(self, email: str) -> UserRecord | None: ...
    async def get_user_by_id(self, user_id: str) -> UserRecord | None: ...
    async def list_projects(self, user_id: str) -> list[ProjectRecord]: ...
    async def create_project(
        self,
        user_id: str,
        name: str,
        description: str | None,
        environment_default: str,
    ) -> ProjectRecord: ...
    async def get_project(self, project_id: str, user_id: str) -> ProjectRecord | None: ...
    async def update_project(
        self,
        project_id: str,
        user_id: str,
        name: str | None,
        description: str | None,
        environment_default: str | None,
    ) -> ProjectRecord | None: ...
    async def create_api_key(
        self,
        project_id: str,
        name: str,
        key_hash: str,
        key_prefix: str,
    ) -> ApiKeyRecord: ...
    async def list_api_keys(self, project_id: str) -> list[ApiKeyRecord]: ...
    async def get_api_key(self, key_id: str) -> ApiKeyRecord | None: ...
    async def get_api_key_by_prefix(self, key_prefix: str) -> ApiKeyRecord | None: ...
    async def mark_api_key_used(self, key_id: str) -> ApiKeyRecord | None: ...
    async def revoke_api_key(self, key_id: str) -> ApiKeyRecord | None: ...
    async def create_worker_job(
        self,
        job_type: str,
        entity_id: str | None,
        payload: dict,
        max_attempts: int,
    ) -> WorkerJobRecord: ...


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class InMemoryMetadataStore:
    def __init__(self) -> None:
        self.users: dict[str, UserRecord] = {}
        self.projects: dict[str, ProjectRecord] = {}
        self.api_keys: dict[str, ApiKeyRecord] = {}
        self.worker_jobs: dict[str, WorkerJobRecord] = {}

    async def create_user(self, email: str, password_hash: str) -> UserRecord:
        if await self.get_user_by_email(email):
            raise DuplicateEmailError(email)

        user = UserRecord(
            id=str(uuid4()),
            email=email,
            password_hash=password_hash,
            created_at=utc_now(),
        )
        self.users[user.id] = user
        return user

    async def get_user_by_email(self, email: str) -> UserRecord | None:
        return next((user for user in self.users.values() if user.email == email), None)

    async def get_user_by_id(self, user_id: str) -> UserRecord | None:
        return self.users.get(user_id)

    async def list_projects(self, user_id: str) -> list[ProjectRecord]:
        return [project for project in self.projects.values() if project.user_id == user_id]

    async def create_project(
        self,
        user_id: str,
        name: str,
        description: str | None,
        environment_default: str,
    ) -> ProjectRecord:
        slug = self._unique_slug(user_id, slugify(name))
        now = utc_now()
        project = ProjectRecord(
            id=str(uuid4()),
            user_id=user_id,
            name=name,
            slug=slug,
            description=description,
            environment_default=environment_default,
            created_at=now,
            updated_at=now,
        )
        self.projects[project.id] = project
        return project

    async def get_project(self, project_id: str, user_id: str) -> ProjectRecord | None:
        project = self.projects.get(project_id)
        if project is None or project.user_id != user_id:
            return None
        return project

    async def update_project(
        self,
        project_id: str,
        user_id: str,
        name: str | None,
        description: str | None,
        environment_default: str | None,
    ) -> ProjectRecord | None:
        project = await self.get_project(project_id, user_id)
        if project is None:
            return None

        new_name = name if name is not None else project.name
        new_slug = project.slug
        if name is not None and slugify(name) != project.slug:
            new_slug = self._unique_slug(user_id, slugify(name), ignore_project_id=project_id)

        updated = ProjectRecord(
            id=project.id,
            user_id=project.user_id,
            name=new_name,
            slug=new_slug,
            description=description if description is not None else project.description,
            environment_default=environment_default or project.environment_default,
            created_at=project.created_at,
            updated_at=utc_now(),
        )
        self.projects[project.id] = updated
        return updated

    async def create_api_key(
        self,
        project_id: str,
        name: str,
        key_hash: str,
        key_prefix: str,
    ) -> ApiKeyRecord:
        api_key = ApiKeyRecord(
            id=str(uuid4()),
            project_id=project_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            created_at=utc_now(),
            last_used_at=None,
            revoked_at=None,
        )
        self.api_keys[api_key.id] = api_key
        return api_key

    async def list_api_keys(self, project_id: str) -> list[ApiKeyRecord]:
        return [key for key in self.api_keys.values() if key.project_id == project_id]

    async def get_api_key(self, key_id: str) -> ApiKeyRecord | None:
        return self.api_keys.get(key_id)

    async def get_api_key_by_prefix(self, key_prefix: str) -> ApiKeyRecord | None:
        return next((key for key in self.api_keys.values() if key.key_prefix == key_prefix), None)

    async def mark_api_key_used(self, key_id: str) -> ApiKeyRecord | None:
        api_key = self.api_keys.get(key_id)
        if api_key is None:
            return None

        used = ApiKeyRecord(
            id=api_key.id,
            project_id=api_key.project_id,
            name=api_key.name,
            key_hash=api_key.key_hash,
            key_prefix=api_key.key_prefix,
            created_at=api_key.created_at,
            last_used_at=utc_now(),
            revoked_at=api_key.revoked_at,
        )
        self.api_keys[key_id] = used
        return used

    async def revoke_api_key(self, key_id: str) -> ApiKeyRecord | None:
        api_key = self.api_keys.get(key_id)
        if api_key is None:
            return None

        revoked = ApiKeyRecord(
            id=api_key.id,
            project_id=api_key.project_id,
            name=api_key.name,
            key_hash=api_key.key_hash,
            key_prefix=api_key.key_prefix,
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at,
            revoked_at=api_key.revoked_at or utc_now(),
        )
        self.api_keys[key_id] = revoked
        return revoked

    async def create_worker_job(
        self,
        job_type: str,
        entity_id: str | None,
        payload: dict,
        max_attempts: int,
    ) -> WorkerJobRecord:
        job = WorkerJobRecord(
            id=str(uuid4()),
            job_type=job_type,
            entity_id=entity_id,
            status="queued",
            attempts=0,
            max_attempts=max_attempts,
            error_message=None,
            payload=payload,
            created_at=utc_now(),
            started_at=None,
            completed_at=None,
        )
        self.worker_jobs[job.id] = job
        return job

    def _unique_slug(
        self,
        user_id: str,
        base_slug: str,
        ignore_project_id: str | None = None,
    ) -> str:
        slug = base_slug
        suffix = 2
        used = {
            project.slug
            for project in self.projects.values()
            if project.user_id == user_id and project.id != ignore_project_id
        }
        while slug in used:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        return slug


class PostgresMetadataStore:
    async def create_user(self, email: str, password_hash: str) -> UserRecord:
        user_id = str(uuid4())
        async with (await get_pool()).connection() as conn:
            try:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        """
                        INSERT INTO users (id, email, password_hash)
                        VALUES (%s, %s, %s)
                        RETURNING id::text, email, password_hash, created_at::text
                        """,
                        (user_id, email, password_hash),
                    )
                    row = await cur.fetchone()
            except Exception as exc:
                if "users_email_key" in str(exc):
                    raise DuplicateEmailError(email) from exc
                raise
        return _user_from_row(row)

    async def get_user_by_email(self, email: str) -> UserRecord | None:
        async with (await get_pool()).connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id::text, email, password_hash, created_at::text
                    FROM users
                    WHERE email = %s
                    """,
                    (email,),
                )
                row = await cur.fetchone()
        return _user_from_row(row) if row else None

    async def get_user_by_id(self, user_id: str) -> UserRecord | None:
        async with (await get_pool()).connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id::text, email, password_hash, created_at::text
                    FROM users
                    WHERE id = %s
                    """,
                    (user_id,),
                )
                row = await cur.fetchone()
        return _user_from_row(row) if row else None

    async def list_projects(self, user_id: str) -> list[ProjectRecord]:
        async with (await get_pool()).connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id::text, user_id::text, name, slug, description,
                           environment_default, created_at::text, updated_at::text
                    FROM projects
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    """,
                    (user_id,),
                )
                rows = await cur.fetchall()
        return [_project_from_row(row) for row in rows]

    async def create_project(
        self,
        user_id: str,
        name: str,
        description: str | None,
        environment_default: str,
    ) -> ProjectRecord:
        project_id = str(uuid4())
        slug = slugify(name)
        async with (await get_pool()).connection() as conn:
            try:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        """
                        INSERT INTO projects
                          (id, user_id, name, slug, description, environment_default)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id::text, user_id::text, name, slug, description,
                                  environment_default, created_at::text, updated_at::text
                        """,
                        (project_id, user_id, name, slug, description, environment_default),
                    )
                    row = await cur.fetchone()
            except Exception as exc:
                if "projects_user_id_slug_key" in str(exc):
                    raise DuplicateProjectSlugError(slug) from exc
                raise
        return _project_from_row(row)

    async def get_project(self, project_id: str, user_id: str) -> ProjectRecord | None:
        async with (await get_pool()).connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id::text, user_id::text, name, slug, description,
                           environment_default, created_at::text, updated_at::text
                    FROM projects
                    WHERE id = %s AND user_id = %s
                    """,
                    (project_id, user_id),
                )
                row = await cur.fetchone()
        return _project_from_row(row) if row else None

    async def update_project(
        self,
        project_id: str,
        user_id: str,
        name: str | None,
        description: str | None,
        environment_default: str | None,
    ) -> ProjectRecord | None:
        current = await self.get_project(project_id, user_id)
        if current is None:
            return None

        new_slug = slugify(name) if name is not None else current.slug
        async with (await get_pool()).connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE projects
                    SET name = COALESCE(%s, name),
                        slug = %s,
                        description = COALESCE(%s, description),
                        environment_default = COALESCE(%s, environment_default),
                        updated_at = now()
                    WHERE id = %s AND user_id = %s
                    RETURNING id::text, user_id::text, name, slug, description,
                              environment_default, created_at::text, updated_at::text
                    """,
                    (
                        name,
                        new_slug,
                        description,
                        environment_default,
                        project_id,
                        user_id,
                    ),
                )
                row = await cur.fetchone()
        return _project_from_row(row) if row else None

    async def create_api_key(
        self,
        project_id: str,
        name: str,
        key_hash: str,
        key_prefix: str,
    ) -> ApiKeyRecord:
        key_id = str(uuid4())
        async with (await get_pool()).connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    INSERT INTO api_keys (id, project_id, name, key_hash, key_prefix)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id::text, project_id::text, name, key_hash, key_prefix,
                              created_at::text, last_used_at::text, revoked_at::text
                    """,
                    (key_id, project_id, name, key_hash, key_prefix),
                )
                row = await cur.fetchone()
        return _api_key_from_row(row)

    async def list_api_keys(self, project_id: str) -> list[ApiKeyRecord]:
        async with (await get_pool()).connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id::text, project_id::text, name, key_hash, key_prefix,
                           created_at::text, last_used_at::text, revoked_at::text
                    FROM api_keys
                    WHERE project_id = %s
                    ORDER BY created_at DESC
                    """,
                    (project_id,),
                )
                rows = await cur.fetchall()
        return [_api_key_from_row(row) for row in rows]

    async def get_api_key(self, key_id: str) -> ApiKeyRecord | None:
        async with (await get_pool()).connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id::text, project_id::text, name, key_hash, key_prefix,
                           created_at::text, last_used_at::text, revoked_at::text
                    FROM api_keys
                    WHERE id = %s
                    """,
                    (key_id,),
                )
                row = await cur.fetchone()
        return _api_key_from_row(row) if row else None

    async def get_api_key_by_prefix(self, key_prefix: str) -> ApiKeyRecord | None:
        async with (await get_pool()).connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id::text, project_id::text, name, key_hash, key_prefix,
                           created_at::text, last_used_at::text, revoked_at::text
                    FROM api_keys
                    WHERE key_prefix = %s
                    """,
                    (key_prefix,),
                )
                row = await cur.fetchone()
        return _api_key_from_row(row) if row else None

    async def mark_api_key_used(self, key_id: str) -> ApiKeyRecord | None:
        async with (await get_pool()).connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE api_keys
                    SET last_used_at = now()
                    WHERE id = %s
                    RETURNING id::text, project_id::text, name, key_hash, key_prefix,
                              created_at::text, last_used_at::text, revoked_at::text
                    """,
                    (key_id,),
                )
                row = await cur.fetchone()
        return _api_key_from_row(row) if row else None

    async def revoke_api_key(self, key_id: str) -> ApiKeyRecord | None:
        async with (await get_pool()).connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE api_keys
                    SET revoked_at = COALESCE(revoked_at, now())
                    WHERE id = %s
                    RETURNING id::text, project_id::text, name, key_hash, key_prefix,
                              created_at::text, last_used_at::text, revoked_at::text
                    """,
                    (key_id,),
                )
                row = await cur.fetchone()
        return _api_key_from_row(row) if row else None

    async def create_worker_job(
        self,
        job_type: str,
        entity_id: str | None,
        payload: dict,
        max_attempts: int,
    ) -> WorkerJobRecord:
        job_id = str(uuid4())
        async with (await get_pool()).connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    INSERT INTO worker_jobs
                      (id, job_type, entity_id, status, attempts, max_attempts, payload)
                    VALUES (%s, %s, %s, 'queued', 0, %s, %s)
                    RETURNING id::text, job_type, entity_id::text, status, attempts,
                              max_attempts, error_message, payload, created_at::text,
                              started_at::text, completed_at::text
                    """,
                    (job_id, job_type, entity_id, max_attempts, Jsonb(payload)),
                )
                row = await cur.fetchone()
        return _worker_job_from_row(row)


def _user_from_row(row) -> UserRecord:
    return UserRecord(
        id=str(row["id"]),
        email=row["email"],
        password_hash=row["password_hash"],
        created_at=str(row["created_at"]),
    )


def _project_from_row(row) -> ProjectRecord:
    return ProjectRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        name=row["name"],
        slug=row["slug"],
        description=row["description"],
        environment_default=row["environment_default"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _api_key_from_row(row) -> ApiKeyRecord:
    return ApiKeyRecord(
        id=str(row["id"]),
        project_id=str(row["project_id"]),
        name=row["name"],
        key_hash=row["key_hash"],
        key_prefix=row["key_prefix"],
        created_at=str(row["created_at"]),
        last_used_at=str(row["last_used_at"]) if row["last_used_at"] else None,
        revoked_at=str(row["revoked_at"]) if row["revoked_at"] else None,
    )


def _worker_job_from_row(row) -> WorkerJobRecord:
    return WorkerJobRecord(
        id=str(row["id"]),
        job_type=row["job_type"],
        entity_id=str(row["entity_id"]) if row["entity_id"] else None,
        status=row["status"],
        attempts=row["attempts"],
        max_attempts=row["max_attempts"],
        error_message=row["error_message"],
        payload=row["payload"],
        created_at=str(row["created_at"]),
        started_at=str(row["started_at"]) if row["started_at"] else None,
        completed_at=str(row["completed_at"]) if row["completed_at"] else None,
    )
