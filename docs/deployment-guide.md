# Deployment Guide

## Architecture

```
Internet → Cloudflare Tunnel → uvicorn :8000 → FastAPI
                                                ├── POST /send-sms (SMS API)
                                                ├── /admin/* (Dashboard API + WebSocket)
                                                └── /* (Svelte GUI)
                                                         ↕
                                              /var/spool/sms/ (smstools)
```

FastAPI serves everything (API + static frontend) on a single port. Reads/writes smstools spool directories directly. Cloudflare Tunnel forwards all traffic — no nginx/caddy needed.

## Prerequisites

- Ubuntu/Debian VM with USB 5G modem
- Python 3.11+
- systemd
- cloudflared — [install guide](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)

All other deps (uv, bun, venv, pip packages) are installed automatically by `predeploy.sh`.

## 1. Application Setup

```bash
git clone <repo> /opt/sms-api
cd /opt/sms-api

# Auto-install everything: python venv, uv, bun, deps, systemd service
sudo bash predeploy.sh michaelphan

# Configure secrets
nano passkey.conf
# SECRET_KEY=<random-64-char-string>
# ADMIN_KEY=<random-64-char-string>
# SMS_BASE_DIR=/var/spool/sms

# Add user to smsd group for SMS file access
sudo usermod -aG smsd michaelphan
sudo systemctl restart sms-api
```

## 2. Systemd Service — sms-api

Create `/etc/systemd/system/sms-api.service`:

```ini
[Unit]
Description=SMS API Service
After=network.target

[Service]
Type=simple
User=michaelphan
WorkingDirectory=/opt/sms-api
ExecStart=/opt/sms-api/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable sms-api
sudo systemctl start sms-api
```

## 3. Cloudflare Tunnel Setup

### 3.1 Login & Create Tunnel

```bash
cloudflared tunnel login
cloudflared tunnel create sms-api
```

This creates a tunnel with a UUID (e.g., `abc123-def456...`). Note this ID.

### 3.2 Configure Tunnel

Create `/etc/cloudflared/config.yml`:

```yaml
tunnel: <TUNNEL_UUID>
credentials-file: /home/michaelphan/.cloudflared/<TUNNEL_UUID>.json

ingress:
  - hostname: sms.sonpython.com
    service: http://127.0.0.1:8000
    originRequest:
      # WebSocket support for /admin/ws
      noTLSVerify: false
  - service: http_status:404
```

**Key points:**
- Single hostname → single uvicorn port handles everything
- WebSocket (`/admin/ws`) works through Cloudflare Tunnel by default
- No need for separate frontend/backend hostnames

### 3.3 DNS Route

```bash
cloudflared tunnel route dns sms-api sms.sonpython.com
```

This creates a CNAME record pointing `sms.sonpython.com` → `<TUNNEL_UUID>.cfargotunnel.com`.

### 3.4 Systemd Service — cloudflared

Create `/etc/systemd/system/cloudflared.service`:

```ini
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=michaelphan
ExecStart=/usr/bin/cloudflared tunnel --config /etc/cloudflared/config.yml run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

## 4. CI/CD — GitHub Self-hosted Runner

### 4.1 Install Runner

```bash
# Go to: GitHub repo → Settings → Actions → Runners → New self-hosted runner
# Follow Linux x64 instructions to download & configure
cd /opt/actions-runner
sudo ./svc.sh install
sudo ./svc.sh start
```

### 4.2 Sudoers for Deploy

```bash
echo "michaelphan ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart sms-api" \
  | sudo tee /etc/sudoers.d/sms-api-deploy
```

### 4.3 Deploy Flow

Push to `main` → GitHub Actions → self-hosted runner:
1. `git pull origin main` (workflow step)
2. `uv pip install -r requirements.txt` (deploy.sh)
3. `bun install && bun run build` (frontend)
4. `sudo systemctl restart sms-api`

cloudflared stays running — no restart needed on code changes.

## 5. Verify

```bash
# Check services
sudo systemctl status sms-api
sudo systemctl status cloudflared

# Test API
curl -X POST https://sms.sonpython.com/send-sms \
  -d "sdt=0901234567" \
  -d "noidungtinnhan=Test" \
  -d "hash=<md5>"

# Test admin (browser)
# https://sms.sonpython.com/ → Login with ADMIN_KEY
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| 502 Bad Gateway | `systemctl status sms-api` — uvicorn not running |
| WebSocket disconnects | Check cloudflared config has no `connectTimeout` too low |
| Deploy fails `uv/bun not found` | Run `predeploy.sh` or check PATH in deploy.sh |
| Permission denied restart | Check sudoers entry in step 4.2 |
| No SMS files visible | `sudo usermod -aG smsd michaelphan` + restart service |
