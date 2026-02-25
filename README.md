# SMS API Service

A lightweight SMS gateway with **admin dashboard** built with **FastAPI + Svelte**, designed to send SMS via HTTP API with **MD5 signature verification** and manage SMS files through a real-time web interface.
Deployed securely via **Cloudflare Tunnel** — no inbound ports required.

## Features

- **SMS API** — Send SMS via HTTP POST with MD5 signature verification
- **Admin Dashboard** — JWT-authenticated web UI to browse/search SMS files
- **Real-time Updates** — WebSocket-powered live file monitoring
- **Send Test SMS** — Admin can send test messages directly from the dashboard
- **File Browser** — View incoming, sent, failed, outgoing, checked folders
- **Phone & Message Preview** — Extracted from SMS file content (From:/To: headers)
- **Mobile Responsive** — Optimized layout for phone screens
- **CI/CD** — Auto-deploy on push via GitHub Actions + self-hosted runner
- **smstools Compatible** — File-based SMS queue (`/var/spool/sms/`)
- **Cloudflare Tunnel** — Zero-trust deployment, no public ports

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI + Uvicorn |
| Frontend | Svelte 5 + Vite |
| Auth | JWT (python-jose) |
| Build | Bun |
| Deploy | systemd + Cloudflare Tunnel |
| CI/CD | GitHub Actions (self-hosted runner) |
| Python Deps | uv |

## Quick Start (Local)

```bash
# Docker
docker compose up --build
# → http://localhost:8000
# Login with ADMIN_KEY from passkey.conf.example
```

## API Endpoint

```
POST /send-sms
Content-Type: application/x-www-form-urlencoded
```

### Parameters

| Name | Required | Description |
|------|----------|-------------|
| `sdt` | Yes | Phone number |
| `noidungtinnhan` | Yes | SMS message content |
| `hash` | Yes | MD5 signature |

### Signature (MD5)

```
MD5("{sdt}&{noidungtinnhan}&{SECRET_KEY}")
```

- Encoding: UTF-8, Output: lowercase hex

### Example

```bash
curl -X POST https://sms.sonpython.com/send-sms \
  -d "sdt=0901234567" \
  -d "noidungtinnhan=Test SMS" \
  -d "hash=$(echo -n '0901234567&Test SMS&YOUR_SECRET_KEY' | md5sum | cut -d' ' -f1)"
```

### Responses

```json
// Success
{"status": "OK", "file": "sms_1734539200_0901234567.sms"}

// Error
{"detail": "INVALID_HASH"}  // 403
```

## Admin Dashboard

Access at `/` after login with `ADMIN_KEY`.

- Browse SMS folders (incoming, sent, failed, outgoing, checked)
- Search by filename, sort by name/date
- View file content in modal
- Send test SMS to any number
- Real-time WebSocket updates (live indicator)
- Pagination (50 per page)

## Production Deployment

```bash
# 1. Clone to VM
git clone <repo> /opt/sms-api

# 2. Run pre-deploy setup (installs all deps)
sudo bash predeploy.sh michaelphan

# 3. Configure
nano /opt/sms-api/passkey.conf
# SECRET_KEY=<random-64-char>
# ADMIN_KEY=<random-64-char>

# 4. Setup Cloudflare Tunnel (see docs/deployment-guide.md)

# 5. Push to main → auto deploy
```

See [docs/deployment-guide.md](docs/deployment-guide.md) for full setup.

## Configuration

`passkey.conf` (never commit):

```ini
SECRET_KEY=your-secret-for-md5-and-jwt
ADMIN_KEY=your-admin-login-key
SMS_BASE_DIR=/var/spool/sms
```

## Security

- Secret keys stored outside repository (`passkey.conf`)
- JWT tokens expire in 24h
- MD5 signature required for every API call
- Path traversal prevention on file access
- WebSocket auth via token query param

## License

MIT
