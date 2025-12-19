import hashlib
import os
import time
from fastapi import FastAPI, HTTPException, Form
from config import load_secret

SMS_OUTGOING_DIR = "/var/spool/sms/outgoing"
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
