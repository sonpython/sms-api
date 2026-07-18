import hashlib
import os
import re
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Form
from fastapi.staticfiles import StaticFiles

from config import load_secret, load_sms_base_dir

SMS_OUTGOING_DIR = os.path.join(load_sms_base_dir(), "outgoing")
SECRET_KEY = load_secret()

app = FastAPI()


def verify_md5(phone: str, message: str, client_hash: str) -> bool:
    raw = f"{phone}&{message}&{SECRET_KEY}"
    md5 = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return md5 == client_hash.lower()


def create_sms_file(phone: str, message: str):
    # Millisecond timestamp: two requests in the same second must not
    # collide on the same filename (the later write would silently
    # overwrite and drop the earlier SMS).
    ts = int(time.time() * 1000)
    filename = f"sms_{ts}_{phone}.sms"
    path = os.path.join(SMS_OUTGOING_DIR, filename)

    content = f"""To: {phone}

{message}
"""

    # smsd scans outgoing/ continuously and will pick up half-written
    # files (empty To:/body -> modem CMS ERROR 500 -> smsd blocks 3600s).
    # smsd ignores *.LOCK files, so write locked then rename (atomic).
    lock_path = path + ".LOCK"
    with open(lock_path, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.rename(lock_path, path)

    return filename


@app.post("/send-sms")
def send_sms(
    sdt: str = Form(...),
    noidungtinnhan: str = Form(...),
    hash: str = Form(...)
):
    if not verify_md5(sdt, noidungtinnhan, hash):
        raise HTTPException(status_code=403, detail="INVALID_HASH")

    # Reject malformed input: an empty/garbage To: header makes the modem
    # fail with CMS ERROR 500 and smsd block all traffic for 3600s.
    if not re.fullmatch(r"\+?\d{8,15}", sdt.strip()):
        raise HTTPException(status_code=400, detail="INVALID_PHONE")
    if not noidungtinnhan.strip():
        raise HTTPException(status_code=400, detail="EMPTY_MESSAGE")

    filename = create_sms_file(sdt.strip(), noidungtinnhan)

    return {
        "status": "OK",
        "file": filename
    }


# Mount admin routes (must be before static files)
from importlib import import_module
admin_routes = import_module("admin-routes")
app.include_router(admin_routes.router)

# Serve Svelte frontend static files (mount last to avoid route conflicts)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
