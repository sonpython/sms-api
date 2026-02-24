#!/bin/bash
set -e

# Resolve home dir for tool paths (handles runner env where $HOME may differ)
REAL_HOME=$(eval echo ~$(whoami))
export PATH="$REAL_HOME/.local/bin:$REAL_HOME/.cargo/bin:$REAL_HOME/.bun/bin:/usr/local/bin:$PATH"

PROJECT_DIR="/opt/sms-api"
SERVICE_NAME="sms-api"

echo "=== SMS API Deploy ==="
echo "HOME=$REAL_HOME, USER=$(whoami)"
echo "PATH=$PATH"
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
