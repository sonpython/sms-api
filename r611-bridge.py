"""Bridge between the smstools-style spool dirs and a 4G router R611 Pro web API.

Replaces smsd (USB modem) while keeping the spool layout that main.py, the admin
UI and the websocket watcher already rely on:

  outgoing/ (+ leftover checked/)  -> POST cx_sms SendSMSInfo -> sent/ | failed/
  router inbox (GetRecvSMSInfo)    -> incoming/ files, then DeleteSMSInfo on router

Router API (reverse engineered from js/panel/SMS/SMS.js): multipart form POST to
/cgi-bin/cx_sms, text fields are UCS-2 hex (4 hex digits per UTF-16 unit).
"""

import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

from config import _load_config, load_sms_base_dir

log = logging.getLogger("r611-bridge")

CFG = _load_config()
ROUTER_URL = CFG.get("R611_URL", "http://192.168.1.170").rstrip("/")
SEND_POLL_SEC = float(CFG.get("R611_SEND_POLL_SEC", "2"))
INBOX_POLL_SEC = float(CFG.get("R611_INBOX_POLL_SEC", "60"))
# After a router timeout, back off: the modem AT channel wedges for many minutes when
# requests pile up, so hammering it only makes recovery slower.
BACKOFF_SEC = float(CFG.get("R611_BACKOFF_SEC", "300"))
# One SendSMSInfo can take ~2 min on this router (each internal AT step may wait
# for a timeout), so the HTTP timeout must be longer than the whole send.
HTTP_TIMEOUT = float(CFG.get("R611_HTTP_TIMEOUT", "180"))
MAX_SEND_ATTEMPTS = 3

BASE = Path(load_sms_base_dir())
OUTGOING_DIRS = [BASE / "outgoing", BASE / "checked"]
SENT_DIR, FAILED_DIR, INCOMING_DIR = BASE / "sent", BASE / "failed", BASE / "incoming"

# Per-file counter of router-side rejections (result != 0). Network errors do
# not count: the message simply waits for the router to come back.
_attempts: dict[str, int] = {}


def ucs2_encode(text: str) -> str:
    return text.encode("utf-16-be", errors="replace").hex().upper()


def ucs2_decode(value: str) -> str:
    s = (value or "").strip()
    if not s or len(s) % 2 or not re.fullmatch(r"[0-9A-Fa-f]+", s):
        return value or ""
    try:
        raw = bytes.fromhex(s)
    except ValueError:
        return value
    # 7-bit/ASCII messages arrive as 2 hex digits per byte, UCS-2 ones as 4 per
    # character; treating an ASCII payload as UCS-2 yields CJK garbage.
    if all(32 <= b <= 126 or b in (9, 10, 13) for b in raw):
        return raw.decode("ascii")
    return raw.decode("utf-16-be", errors="replace")


def router_post(page: str, **fields) -> dict:
    # files= forces multipart/form-data, which is what the web UI (FormData) sends.
    form = {"Page": (None, page), **{k: (None, str(v)) for k, v in fields.items()}}
    # The router's HTTP server never answers a keep-alive request that advertises
    # gzip (python-requests defaults); curl-like plain headers work.
    headers = {"Connection": "close", "Accept-Encoding": "identity"}
    r = requests.post(f"{ROUTER_URL}/cgi-bin/cx_sms", files=form, headers=headers, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    # The router emits raw UTF-8 without a charset header; requests would guess
    # latin-1 and turn Vietnamese text into mojibake.
    return json.loads(r.content.decode("utf-8", errors="replace"))


def parse_spool_file(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    head, _, body = text.partition("\n\n")
    phone = ""
    for line in head.splitlines():
        if line.startswith("To:"):
            phone = line.split(":", 1)[1].strip()
    return phone, body.rstrip("\n")


def write_result(dest_dir: Path, path: Path, headers: list[str], body: str):
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / path.name).write_text("\n".join(headers) + "\n\n" + body + "\n", encoding="utf-8")
    path.unlink(missing_ok=True)
    _attempts.pop(path.name, None)


def process_outgoing():
    for d in OUTGOING_DIRS:
        if not d.exists():
            continue
        for path in sorted(d.glob("*.sms")):
            phone, body = parse_spool_file(path)
            stamp = datetime.now().strftime("%y-%m-%d %H:%M:%S")
            if not re.fullmatch(r"\+?\d{8,15}", phone) or not body.strip():
                write_result(FAILED_DIR, path, [f"To: {phone}", "Modem: R611", f"Failed: {stamp}",
                                                "Fail_reason: invalid phone or empty body"], body)
                log.warning("invalid spool file %s -> failed", path.name)
                continue
            t0 = time.time()
            try:
                res = router_post("SendSMSInfo", phone=phone, message=ucs2_encode(body))
            except requests.Timeout:
                # The router keeps processing after we give up, so retrying would
                # deliver the same OTP twice. Park it in failed/ for a human.
                write_result(FAILED_DIR, path, [f"To: {phone}", "Modem: R611", f"Failed: {stamp}",
                                                "Fail_reason: router timeout (message may still have been sent)"], body)
                log.error("timeout sending %s; moved to failed, backing off %ss", path.name, BACKOFF_SEC)
                time.sleep(BACKOFF_SEC)
                return
            except requests.RequestException as e:
                log.error("router unreachable while sending %s: %s; backing off %ss", path.name, e, BACKOFF_SEC)
                time.sleep(BACKOFF_SEC)
                return  # keep file, retry next loop
            took = int(time.time() - t0)
            if res.get("result") == 0:
                write_result(SENT_DIR, path, [f"To: {phone}", "Modem: R611", f"Sent: {stamp}",
                                              f"Sending_time: {took}"], body)
                log.info("sent %s to %s in %ss", path.name, phone, took)
            else:
                n = _attempts[path.name] = _attempts.get(path.name, 0) + 1
                log.warning("router rejected %s (%s) attempt %d/%d", path.name, res.get("message"), n, MAX_SEND_ATTEMPTS)
                if n >= MAX_SEND_ATTEMPTS:
                    write_result(FAILED_DIR, path, [f"To: {phone}", "Modem: R611", f"Failed: {stamp}",
                                                    f"Fail_reason: {res.get('message', 'router error')}"], body)


def decode_sender(value: str) -> str:
    """Alphanumeric senders arrive as concatenated decimal char codes
    ("86736984846976" -> "VIETTEL"); numeric senders are returned unchanged."""
    s = (value or "").strip()
    if not s.isdigit() or len(s) < 4 or s.startswith(("0", "84")):
        return s
    out, i = "", 0
    while i < len(s):
        for width in (3, 2):
            chunk = s[i:i + width]
            if len(chunk) == width and 32 <= int(chunk) <= 126:
                out += chr(int(chunk)); i += width; break
        else:
            return s  # not a char-code sequence after all
    return out


def parse_router_time(value: str) -> str:
    # Router format: "26/09/22,16:30:50+28" (yy/mm/dd,hh:mm:ss+tz quarter-hours).
    try:
        return datetime.strptime(value[:17], "%y/%m/%d,%H:%M:%S").strftime("%y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return value or ""


def process_inbox():
    try:
        res = router_post("GetRecvSMSInfo", pageNumber=1)
    except (requests.RequestException, ValueError) as e:
        log.error("inbox poll failed: %s; backing off %ss", e, BACKOFF_SEC)
        time.sleep(BACKOFF_SEC)
        return
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    for item in res.get("sms_list") or []:
        phone, idx = decode_sender(item.get("phone", "")), item.get("index")
        body = ucs2_decode(item.get("message", ""))
        received = datetime.now().strftime("%y-%m-%d %H:%M:%S")
        name = f"R611.{int(time.time() * 1000)}_{idx}_{phone}.sms"
        headers = [f"From: {phone}", f"Sent: {parse_router_time(item.get('time', ''))}",
                   f"Received: {received}", f"Subject: {body[:40]}", "Modem: R611"]
        (INCOMING_DIR / name).write_text("\n".join(headers) + "\n\n" + body + "\n", encoding="utf-8")
        try:
            # smsType 0 = device memory inbox (the UI's "Device Inbox" tab).
            router_post("DeleteSMSInfo", smsType=0, index_list=idx)
        except requests.RequestException as e:
            log.error("saved %s but could not delete index %s on router: %s", name, idx, e)
            return  # avoid duplicating the rest of the page; retry next poll
        log.info("received from %s -> %s", phone, name)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    log.info("start: router=%s spool=%s", ROUTER_URL, BASE)
    next_inbox = 0.0
    while True:
        process_outgoing()
        if time.time() >= next_inbox:
            process_inbox()
            next_inbox = time.time() + INBOX_POLL_SEC
        time.sleep(SEND_POLL_SEC)


if __name__ == "__main__":
    main()
