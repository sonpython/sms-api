#!/bin/bash
set -e

PROJECT_DIR="/opt/sms-api"
SERVICE_NAME="sms-api"

echo "=== SMS API Deploy ==="
echo "Time: $(date)"

cd "$PROJECT_DIR"

# Pull latest code
echo ">> git pull"
git pull origin main

# Install Python dependencies
echo ">> pip install"
pip install -r requirements.txt --quiet

# Build frontend
echo ">> bun build"
cd frontend
bun install --frozen-lockfile
bun run build
cd ..

# Restart API service (cloudflared stays running)
echo ">> restart $SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "=== Deploy complete ==="
