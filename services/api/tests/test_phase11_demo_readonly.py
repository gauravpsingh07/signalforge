import asyncio

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_metadata_store
from app.main import app
from app.services.metadata_store import InMemoryMetadataStore

DEMO_EMAIL = "demo@signalforge.dev"


@pytest.fixture()
def store() -> InMemoryMetadataStore:
    return InMemoryMetadataStore()


@pytest.fixture()
def client(store: InMemoryMetadataStore) -> TestClient:
    app.dependency_overrides[get_metadata_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "correct-password"},
    )
    assert response.status_code == 201
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_demo_user_cannot_create_projects(client: TestClient) -> None:
    token = register(client, DEMO_EMAIL)["access_token"]

    response = client.post(
        "/projects",
        json={"name": "Demo Sneak Project"},
        headers=auth_headers(token),
    )

    assert response.status_code == 403
    assert "read-only" in response.json()["error"]["message"]


def test_demo_user_cannot_create_api_keys(
    client: TestClient,
    store: InMemoryMetadataStore,
) -> None:
    data = register(client, DEMO_EMAIL)
    token = data["access_token"]
    project = asyncio.run(
        store.create_project(
            user_id=data["user"]["id"],
            name="Checkout Demo",
            description=None,
            environment_default="production",
        )
    )

    response = client.post(
        f"/projects/{project.id}/api-keys",
        json={"name": "sneaky-key"},
        headers=auth_headers(token),
    )

    assert response.status_code == 403


def test_demo_user_can_still_read_projects(
    client: TestClient,
    store: InMemoryMetadataStore,
) -> None:
    data = register(client, DEMO_EMAIL)
    token = data["access_token"]
    asyncio.run(
        store.create_project(
            user_id=data["user"]["id"],
            name="Checkout Demo",
            description=None,
            environment_default="production",
        )
    )

    response = client.get("/projects", headers=auth_headers(token))

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_regular_users_are_unaffected(client: TestClient) -> None:
    token = register(client, "dev@example.com")["access_token"]

    response = client.post(
        "/projects",
        json={"name": "My Real Project"},
        headers=auth_headers(token),
    )

    assert response.status_code == 201
