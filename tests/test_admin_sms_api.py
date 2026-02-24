"""Tests for admin SMS listing, reading, search, sort endpoints."""
import os
import time

from tests.conftest import SMS_TMP_DIR


def _create_sms_file(folder, filename, content="To: 0901234567\n\nHello"):
    path = os.path.join(SMS_TMP_DIR, folder, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


# --- List files ---

def test_list_empty_folder(client, auth_headers):
    resp = client.get("/admin/api/sms/checked", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["files"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["per_page"] == 50


def test_list_files_in_folder(client, auth_headers):
    _create_sms_file("sent", "sms_001.sms")
    _create_sms_file("sent", "sms_002.sms")
    resp = client.get("/admin/api/sms/sent", headers=auth_headers)
    data = resp.json()
    assert data["total"] >= 2
    filenames = [f["filename"] for f in data["files"]]
    assert "sms_001.sms" in filenames
    assert "sms_002.sms" in filenames


def test_list_invalid_folder(client, auth_headers):
    resp = client.get("/admin/api/sms/invalid_folder", headers=auth_headers)
    assert resp.status_code == 400


def test_list_ignores_hidden_files(client, auth_headers):
    _create_sms_file("incoming", ".hidden_file")
    _create_sms_file("incoming", "visible.sms")
    resp = client.get("/admin/api/sms/incoming", headers=auth_headers)
    filenames = [f["filename"] for f in resp.json()["files"]]
    assert ".hidden_file" not in filenames
    assert "visible.sms" in filenames


# --- Search ---

def test_search_by_filename(client, auth_headers):
    _create_sms_file("outgoing", "sms_search_target.sms")
    _create_sms_file("outgoing", "sms_other.sms")
    resp = client.get("/admin/api/sms/outgoing?search=search_target", headers=auth_headers)
    data = resp.json()
    assert all("search_target" in f["filename"] for f in data["files"])


def test_search_case_insensitive(client, auth_headers):
    _create_sms_file("outgoing", "SMS_UPPER.sms")
    resp = client.get("/admin/api/sms/outgoing?search=sms_upper", headers=auth_headers)
    filenames = [f["filename"] for f in resp.json()["files"]]
    assert "SMS_UPPER.sms" in filenames


# --- Sort ---

def test_sort_by_name_asc(client, auth_headers):
    _create_sms_file("failed", "aaa.sms")
    _create_sms_file("failed", "zzz.sms")
    resp = client.get("/admin/api/sms/failed?sort_by=name&sort_order=asc", headers=auth_headers)
    files = resp.json()["files"]
    names = [f["filename"] for f in files]
    assert names == sorted(names, key=str.lower)


def test_sort_by_date_desc(client, auth_headers):
    p1 = _create_sms_file("failed", "old.sms")
    time.sleep(0.05)
    p2 = _create_sms_file("failed", "new.sms")
    resp = client.get("/admin/api/sms/failed?sort_by=modified&sort_order=desc", headers=auth_headers)
    files = resp.json()["files"]
    timestamps = [f["modified"] for f in files]
    assert timestamps == sorted(timestamps, reverse=True)


# --- Read file ---

def test_read_sms_file(client, auth_headers):
    content = "To: 0909999999\n\nTest message content"
    _create_sms_file("sent", "read_test.sms", content)
    resp = client.get("/admin/api/sms/sent/read_test.sms", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "read_test.sms"
    assert data["folder"] == "sent"
    assert data["content"] == content


def test_read_nonexistent_file(client, auth_headers):
    resp = client.get("/admin/api/sms/sent/nonexistent.sms", headers=auth_headers)
    assert resp.status_code == 404


def test_read_file_path_traversal(client, auth_headers):
    resp = client.get("/admin/api/sms/sent/../../etc/passwd", headers=auth_headers)
    assert resp.status_code == 404  # Path traversal blocked by Path.name


# --- File metadata ---

def test_file_entry_has_required_fields(client, auth_headers):
    _create_sms_file("incoming", "meta_test.sms")
    resp = client.get("/admin/api/sms/incoming", headers=auth_headers)
    f = next(x for x in resp.json()["files"] if x["filename"] == "meta_test.sms")
    assert "filename" in f
    assert "size" in f
    assert "modified" in f
    assert "modified_iso" in f
