#!/bin/bash
set -e

PROJECT_DIR="/opt/sms-api"
SERVICE_NAME="sms-api"

echo "=== SMS API Deploy ==="
echo "Time: $(date)"

cd "$PROJECT_DIR"

# Install Python dependencies via uv
echo ">> uv install"
uv venv .venv --python 3.13 2>/dev/null || true
uv pip install -r requirements.txt --quiet

# Build frontend
echo ">> bun build"
cd frontend
bun install --frozen-lockfile
bun run build
cd ..

# Restart API service (cloudflared stays running)
echo ">> restart $SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl restart cloudflared 2>/dev/null || true

echo "=== Deploy complete ==="
