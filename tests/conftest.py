import os
import tempfile
import shutil

import pytest

# Create temp passkey.conf before any app imports
_tmp_dir = tempfile.mkdtemp()
_conf_path = os.path.join(_tmp_dir, "passkey.conf")
with open(_conf_path, "w") as f:
    f.write("SECRET_KEY=test_secret\nADMIN_KEY=test_admin\n")
os.environ["PASSKEY_CONF"] = _conf_path

# Create temp SMS directories
SMS_TMP_DIR = os.path.join(_tmp_dir, "sms")
for folder in ["checked", "failed", "incoming", "outgoing", "sent"]:
    os.makedirs(os.path.join(SMS_TMP_DIR, folder))


@pytest.fixture(autouse=True)
def patch_sms_dirs(monkeypatch):
    """Patch SMS directories to use temp dir for all tests."""
    import importlib
    admin_routes = importlib.import_module("admin-routes")
    monkeypatch.setattr(admin_routes, "SMS_BASE_DIR", SMS_TMP_DIR)

    import main
    monkeypatch.setattr(main, "SMS_OUTGOING_DIR", os.path.join(SMS_TMP_DIR, "outgoing"))


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    """Get a valid admin JWT token."""
    resp = client.post("/admin/login", data={"admin_key": "test_admin"})
    return resp.json()["token"]


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_tmp_dir, ignore_errors=True)
