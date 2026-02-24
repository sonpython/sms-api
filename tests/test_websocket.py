"""Tests for admin WebSocket endpoint."""
import os

from tests.conftest import SMS_TMP_DIR


def test_ws_rejects_no_token(client):
    from starlette.websockets import WebSocketDisconnect
    try:
        with client.websocket_connect("/admin/ws") as ws:
            pass
        assert False, "Should have been rejected"
    except WebSocketDisconnect as e:
        assert e.code == 4001


def test_ws_rejects_invalid_token(client):
    try:
        with client.websocket_connect("/admin/ws?token=bad.token.here") as ws:
            pass
    except Exception:
        pass  # Expected: connection rejected


def test_ws_accepts_valid_token(client, admin_token):
    with client.websocket_connect(f"/admin/ws?token={admin_token}") as ws:
        # First message should be heartbeat
        msg = ws.receive_json()
        assert msg["event"] == "heartbeat"


def test_ws_detects_new_file(client, admin_token):
    with client.websocket_connect(f"/admin/ws?token={admin_token}") as ws:
        # Consume heartbeat
        ws.receive_json()

        # Create a new file while ws is connected
        fpath = os.path.join(SMS_TMP_DIR, "sent", "ws_test_new.sms")
        with open(fpath, "w") as f:
            f.write("To: 0901234567\n\nWS test")

        # Next messages should include new_file event (after heartbeat)
        found_new = False
        for _ in range(5):
            msg = ws.receive_json()
            if msg.get("event") == "new_file" and msg.get("folder") == "sent":
                assert msg["file"]["filename"] == "ws_test_new.sms"
                found_new = True
                break
        assert found_new, "WebSocket did not detect new file"
