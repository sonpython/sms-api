"""Tests for POST /send-sms endpoint."""
import hashlib


def _make_hash(phone, message, secret="test_secret"):
    raw = f"{phone}&{message}&{secret}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def test_send_sms_success(client):
    phone = "0901234567"
    msg = "Hello test"
    h = _make_hash(phone, msg)
    resp = client.post("/send-sms", data={"sdt": phone, "noidungtinnhan": msg, "hash": h})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "OK"
    assert phone in data["file"]
    assert data["file"].endswith(".sms")


def test_send_sms_invalid_hash(client):
    resp = client.post("/send-sms", data={"sdt": "0901234567", "noidungtinnhan": "Hi", "hash": "wrong"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "INVALID_HASH"


def test_send_sms_missing_params(client):
    resp = client.post("/send-sms", data={"sdt": "0901234567"})
    assert resp.status_code == 422  # FastAPI validation error


def test_send_sms_hash_case_insensitive(client):
    phone = "0901234567"
    msg = "Test case"
    h = _make_hash(phone, msg).upper()
    resp = client.post("/send-sms", data={"sdt": phone, "noidungtinnhan": msg, "hash": h})
    assert resp.status_code == 200


def test_send_sms_utf8_message(client):
    phone = "0901234567"
    msg = "Xin chào, đây là tin nhắn tiếng Việt"
    h = _make_hash(phone, msg)
    resp = client.post("/send-sms", data={"sdt": phone, "noidungtinnhan": msg, "hash": h})
    assert resp.status_code == 200
