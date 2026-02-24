import hashlib
import os
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
    ts = int(time.time())
    filename = f"sms_{ts}_{phone}.sms"
    path = os.path.join(SMS_OUTGOING_DIR, filename)

    content = f"""To: {phone}

{message}
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return filename


@app.post("/send-sms")
def send_sms(
    sdt: str = Form(...),
    noidungtinnhan: str = Form(...),
    hash: str = Form(...)
):
    if not verify_md5(sdt, noidungtinnhan, hash):
        raise HTTPException(status_code=403, detail="INVALID_HASH")

    filename = create_sms_file(sdt, noidungtinnhan)

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
