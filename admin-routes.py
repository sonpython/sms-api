import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from config import load_secret, load_admin_key

# --- Constants ---

ADMIN_KEY = load_admin_key()
JWT_SECRET = load_secret()  # use SECRET_KEY for JWT signing (separate from ADMIN_KEY)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

SMS_BASE_DIR = "/var/spool/sms"
ALLOWED_FOLDERS = ["checked", "failed", "incoming", "outgoing", "sent"]

router = APIRouter(prefix="/admin")
security = HTTPBearer()


# --- Auth helpers ---

def create_token() -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    return jwt.encode({"exp": expire, "sub": "admin"}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")


# --- Auth endpoint ---

@router.post("/login")
def admin_login(admin_key: str = Form(...)):
    if admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="INVALID_ADMIN_KEY")
    return {"token": create_token()}


# --- SMS file helpers ---

def _parse_sms_file(filepath: Path) -> dict:
    """Parse an smstools .sms file and return metadata + content."""
    stat = filepath.stat()
    result = {
        "filename": filepath.name,
        "folder": filepath.parent.name,
        "size": stat.st_size,
        "modified": stat.st_mtime,
        "modified_iso": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
        result["content"] = text
    except Exception:
        result["content"] = ""
    return result


def _validate_folder(folder: str):
    if folder not in ALLOWED_FOLDERS:
        raise HTTPException(status_code=400, detail=f"Invalid folder. Allowed: {ALLOWED_FOLDERS}")


def _file_entry(f: Path) -> dict:
    """Build file metadata dict with single stat call."""
    stat = f.stat()
    return {
        "filename": f.name,
        "size": stat.st_size,
        "modified": stat.st_mtime,
        "modified_iso": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


# --- SMS API endpoints ---

@router.get("/api/sms/{folder}")
def list_sms_files(
    folder: str,
    sort_by: str = "modified",
    sort_order: str = "desc",
    search: Optional[str] = None,
    _admin: str = Depends(verify_token),
):
    """List SMS files in a folder with optional search and sort."""
    _validate_folder(folder)
    folder_path = Path(SMS_BASE_DIR) / folder

    if not folder_path.exists():
        return {"files": [], "total": 0}

    files = []
    for f in folder_path.iterdir():
        if f.is_file() and not f.name.startswith("."):
            if search and search.lower() not in f.name.lower():
                continue
            files.append(_file_entry(f))

    # Sort
    reverse = sort_order == "desc"
    if sort_by == "name":
        files.sort(key=lambda x: x["filename"].lower(), reverse=reverse)
    else:
        files.sort(key=lambda x: x["modified"], reverse=reverse)

    return {"files": files, "total": len(files)}


@router.get("/api/sms/{folder}/{filename}")
def read_sms_file(
    folder: str,
    filename: str,
    _admin: str = Depends(verify_token),
):
    """Read a specific SMS file content."""
    _validate_folder(folder)

    # Prevent path traversal
    safe_name = Path(filename).name
    filepath = Path(SMS_BASE_DIR) / folder / safe_name

    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")

    return _parse_sms_file(filepath)


# --- WebSocket for realtime updates ---

async def _watch_sms_dirs(websocket: WebSocket):
    """Watch SMS directories and send new/removed file events via WebSocket."""
    known_files: dict[str, set[str]] = {}
    for folder in ALLOWED_FOLDERS:
        folder_path = Path(SMS_BASE_DIR) / folder
        if folder_path.exists():
            known_files[folder] = {f.name for f in folder_path.iterdir() if f.is_file()}
        else:
            known_files[folder] = set()

    while True:
        # Send heartbeat ping to keep connection alive through proxies
        await websocket.send_json({"event": "heartbeat"})
        await asyncio.sleep(2)

        for folder in ALLOWED_FOLDERS:
            folder_path = Path(SMS_BASE_DIR) / folder
            if not folder_path.exists():
                continue

            current_files = {f.name for f in folder_path.iterdir() if f.is_file()}
            new_files = current_files - known_files.get(folder, set())
            removed_files = known_files.get(folder, set()) - current_files

            for fname in new_files:
                fpath = folder_path / fname
                if fpath.exists():
                    await websocket.send_json({
                        "event": "new_file",
                        "folder": folder,
                        "file": _file_entry(fpath),
                    })

            for fname in removed_files:
                await websocket.send_json({
                    "event": "removed_file",
                    "folder": folder,
                    "filename": fname,
                })

            known_files[folder] = current_files


@router.websocket("/ws")
async def sms_websocket(websocket: WebSocket):
    """WebSocket endpoint for realtime SMS file updates. Requires token as query param."""
    token = websocket.query_params.get("token", "")
    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        await websocket.close(code=4001, reason="INVALID_TOKEN")
        return

    await websocket.accept()
    try:
        await _watch_sms_dirs(websocket)
    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close()
