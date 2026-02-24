"""Tests for admin authentication endpoints."""


def test_login_success(client):
    resp = client.post("/admin/login", data={"admin_key": "test_admin"})
    assert resp.status_code == 200
    assert "token" in resp.json()


def test_login_wrong_key(client):
    resp = client.post("/admin/login", data={"admin_key": "wrong_key"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "INVALID_ADMIN_KEY"


def test_login_missing_key(client):
    resp = client.post("/admin/login")
    assert resp.status_code == 422


def test_protected_endpoint_no_token(client):
    resp = client.get("/admin/api/sms/sent")
    assert resp.status_code in (401, 403)  # varies by FastAPI/Starlette version


def test_protected_endpoint_invalid_token(client):
    resp = client.get("/admin/api/sms/sent", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "INVALID_TOKEN"


def test_protected_endpoint_valid_token(client, auth_headers):
    resp = client.get("/admin/api/sms/sent", headers=auth_headers)
    assert resp.status_code == 200
