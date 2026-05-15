import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_metadata_store
from app.main import app
from app.services.metadata_store import InMemoryMetadataStore


@pytest.fixture()
def client() -> TestClient:
    store = InMemoryMetadataStore()
    app.dependency_overrides[get_metadata_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register(client: TestClient, email: str = "dev@example.com") -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "correct-password"},
    )
    assert response.status_code == 201
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_user(client: TestClient) -> None:
    data = register(client)

    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["email"] == "dev@example.com"
    assert "password_hash" not in data["user"]


def test_duplicate_user_fails(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/auth/register",
        json={"email": "DEV@example.com", "password": "correct-password"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["message"] == "Email is already registered"


def test_login_works(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/auth/login",
        json={"email": "dev@example.com", "password": "correct-password"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_invalid_login_fails(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/auth/login",
        json={"email": "dev@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_create_project(client: TestClient) -> None:
    token = register(client)["access_token"]

    response = client.post(
        "/projects",
        headers=auth_headers(token),
        json={
            "name": "Checkout Service Demo",
            "description": "Demo checkout observability project",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Checkout Service Demo"
    assert data["slug"] == "checkout-service-demo"
    assert data["environment_default"] == "production"


def test_user_cannot_access_another_users_project(client: TestClient) -> None:
    first_token = register(client, "first@example.com")["access_token"]
    second_token = register(client, "second@example.com")["access_token"]
    project = client.post(
        "/projects",
        headers=auth_headers(first_token),
        json={"name": "Private Project"},
    ).json()

    response = client.get(
        f"/projects/{project['id']}",
        headers=auth_headers(second_token),
    )

    assert response.status_code == 404


def test_create_api_key_returns_raw_key_once(client: TestClient) -> None:
    token = register(client)["access_token"]
    project = client.post(
        "/projects",
        headers=auth_headers(token),
        json={"name": "Checkout Service Demo"},
    ).json()

    response = client.post(
        f"/projects/{project['id']}/api-keys",
        headers=auth_headers(token),
        json={"name": "Local demo key", "mode": "demo"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["raw_key"].startswith("sf_demo_")
    assert data["key_prefix"] == data["raw_key"][:16]


def test_listing_api_keys_does_not_expose_raw_key(client: TestClient) -> None:
    token = register(client)["access_token"]
    project = client.post(
        "/projects",
        headers=auth_headers(token),
        json={"name": "Checkout Service Demo"},
    ).json()
    created = client.post(
        f"/projects/{project['id']}/api-keys",
        headers=auth_headers(token),
        json={"name": "Local demo key"},
    ).json()

    response = client.get(
        f"/projects/{project['id']}/api-keys",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "raw_key" not in data[0]
    assert "key_hash" not in data[0]
    assert created["raw_key"] not in str(data)


def test_revoking_api_key_works(client: TestClient) -> None:
    token = register(client)["access_token"]
    project = client.post(
        "/projects",
        headers=auth_headers(token),
        json={"name": "Checkout Service Demo"},
    ).json()
    key = client.post(
        f"/projects/{project['id']}/api-keys",
        headers=auth_headers(token),
        json={"name": "Local demo key"},
    ).json()

    response = client.delete(
        f"/api-keys/{key['id']}",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_revoked"] is True
    assert data["revoked_at"] is not None
