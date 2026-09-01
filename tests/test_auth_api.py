import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_db_manager
from app.db.database import FirestoreManager
from fake_firestore import FakeFirestoreClient


@pytest.fixture
def fake_db():
    return FirestoreManager(FakeFirestoreClient())


@pytest.fixture
def client(fake_db):
    app.dependency_overrides[get_db_manager] = lambda: fake_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_auth_me_local_dev(client):
    """Test /api/auth/me returns local dev profile with admin status in local mode."""
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer local_dev_token"})
    assert res.status_code == 200
    data = res.json()
    assert data["uid"] == "local_dev_user"
    assert data["role"] == "admin"
    assert data["is_approved"] is True
    assert data["is_admin"] is True


def test_auth_invite_and_list_users(client, fake_db):
    """Test admin can invite a user and list authorized users."""
    # 1. Invite a new user
    res = client.post(
        "/api/auth/invite",
        json={"email": "newdesigner@studio.com", "role": "user"},
        headers={"Authorization": "Bearer local_dev_token"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["user"]["email"] == "newdesigner@studio.com"
    assert data["user"]["status"] == "pending_invite"

    # 2. List users
    res = client.get(
        "/api/auth/users",
        headers={"Authorization": "Bearer local_dev_token"},
    )
    assert res.status_code == 200
    list_data = res.json()
    assert "users" in list_data
    assert "summary" in list_data
    assert list_data["summary"]["total_users"] >= 1
    assert any(u["email"] == "newdesigner@studio.com" for u in list_data["users"])


def test_auth_update_status_and_delete(client, fake_db):
    """Test updating user status and deleting a user."""
    # Create an invite
    fake_db.create_user_invite("tobedeleted@studio.com", role="user")

    # Update status to disabled
    res = client.patch(
        "/api/auth/users/invite_tobedeleted@studio.com/status",
        json={"status": "disabled"},
        headers={"Authorization": "Bearer local_dev_token"},
    )
    assert res.status_code == 200
    assert res.json()["user"]["status"] == "disabled"

    # Delete user
    del_res = client.delete(
        "/api/auth/users/invite_tobedeleted@studio.com",
        headers={"Authorization": "Bearer local_dev_token"},
    )
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"
