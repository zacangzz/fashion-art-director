import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_db_manager
from app.db.database import FirestoreManager
from fake_firestore import FakeFirestoreClient


@pytest.fixture
def fake_db():
    manager = FirestoreManager(FakeFirestoreClient())
    
    # Seed admin user
    manager.activate_user_on_login(
        uid="admin_uid",
        email="admin@studio.com",
        display_name="Admin Director",
        is_bootstrap_admin=True,
    )
    
    # Seed target active designer
    manager.activate_user_on_login(
        uid="target_user_1",
        email="designer@studio.com",
        display_name="Senior Designer",
        is_bootstrap_admin=False,
    )
    manager.update_user_status("target_user_1", status="approved", role="user")
    
    # Seed pending invite user
    manager.create_user_invite(
        email="intern@studio.com",
        role="user",
        invited_by="admin@studio.com",
    )
    
    # Seed regular user
    manager.activate_user_on_login(
        uid="regular_user_3",
        email="regular@studio.com",
        display_name="Regular User",
        is_bootstrap_admin=False,
    )
    manager.update_user_status("regular_user_3", status="approved", role="user")
    
    return manager


@pytest.fixture
def client(fake_db):
    app.dependency_overrides[get_db_manager] = lambda: fake_db
    with patch("app.auth.firebase_auth.get_db_manager", return_value=fake_db):
        with TestClient(app) as test_client:
            yield test_client
    app.dependency_overrides.clear()


def test_normal_admin_profile(client):
    """Admin calling /api/auth/me without proxy header gets own profile."""
    with patch("app.auth.firebase_auth.get_raw_user") as mock_auth:
        mock_auth.return_value = {
            "uid": "admin_uid",
            "email": "admin@studio.com",
            "name": "Admin Director",
            "is_anonymous": False,
        }
        res = client.get("/api/auth/me")
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == "admin@studio.com"
        assert data["role"] == "admin"
        assert data["is_admin"] is True
        assert data["is_proxy"] is False
        assert data["proxied_by"] is None


def test_admin_can_proxy_existing_user(client):
    """Admin calling /api/auth/me with X-Proxy-User-Id gets proxied profile."""
    with patch("app.auth.firebase_auth.get_raw_user") as mock_auth:
        mock_auth.return_value = {
            "uid": "admin_uid",
            "email": "admin@studio.com",
            "name": "Admin Director",
            "is_anonymous": False,
        }
        res = client.get(
            "/api/auth/me",
            headers={"X-Proxy-User-Id": "target_user_1"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == "target_user_1"
        assert data["uid"] == "target_user_1"
        assert data["email"] == "designer@studio.com"
        assert data["display_name"] == "Senior Designer"
        assert data["role"] == "user"
        assert data["is_admin"] is False
        assert data["is_approved"] is True
        assert data["is_proxy"] is True
        assert data["proxied_by"]["email"] == "admin@studio.com"
        assert data["real_user"]["role"] == "admin"


def test_non_admin_cannot_proxy(client):
    """Non-admin user attempting to send X-Proxy-User-Id receives 403 Forbidden."""
    with patch("app.auth.firebase_auth.get_raw_user") as mock_auth:
        mock_auth.return_value = {
            "uid": "regular_user_3",
            "email": "regular@studio.com",
            "name": "Regular User",
            "is_anonymous": False,
        }
        res = client.get(
            "/api/auth/me",
            headers={"X-Proxy-User-Id": "target_user_1"},
        )
        assert res.status_code == 403
        assert "Administrative privileges required" in res.json()["detail"]


def test_admin_proxy_nonexistent_user_returns_404(client):
    """Admin attempting to proxy a non-existent user receives 404 Not Found."""
    with patch("app.auth.firebase_auth.get_raw_user") as mock_auth:
        mock_auth.return_value = {
            "uid": "admin_uid",
            "email": "admin@studio.com",
            "name": "Admin Director",
            "is_anonymous": False,
        }
        res = client.get(
            "/api/auth/me",
            headers={"X-Proxy-User-Id": "nonexistent_ghost_id"},
        )
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


def test_admin_routes_accessible_while_proxying(client):
    """Admin proxying as regular user can still access admin-only endpoints (/api/auth/users)."""
    with patch("app.auth.firebase_auth.get_raw_user") as mock_auth:
        mock_auth.return_value = {
            "uid": "admin_uid",
            "email": "admin@studio.com",
            "name": "Admin Director",
            "is_anonymous": False,
        }
        res = client.get(
            "/api/auth/users",
            headers={"X-Proxy-User-Id": "target_user_1"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "users" in data
        assert len(data["users"]) >= 3


def test_strict_mirroring_unapproved_target(client, fake_db):
    """Admin proxying a pending_invite user receives 403 when accessing protected generation endpoints."""
    with patch("app.auth.firebase_auth.get_raw_user") as mock_auth:
        mock_auth.return_value = {
            "uid": "admin_uid",
            "email": "admin@studio.com",
            "name": "Admin Director",
            "is_anonymous": False,
        }
        # /api/history requires get_current_user (approved whitelist)
        res = client.get(
            "/api/history",
            headers={"X-Proxy-User-Id": "invite_intern@studio.com"},
        )
        assert res.status_code == 403
        assert "Access restricted" in res.json()["detail"]


def test_local_dev_user_can_proxy(client):
    """Local dev user (with Bearer local_dev_token) can proxy into another user."""
    res = client.get(
        "/api/auth/me",
        headers={
            "Authorization": "Bearer local_dev_token",
            "X-Proxy-User-Id": "target_user_1",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["uid"] == "target_user_1"
    assert data["is_proxy"] is True
    assert data["proxied_by"]["uid"] == "local_dev_user"
