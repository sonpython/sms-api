#!/bin/bash
# Pre-deploy setup: installs all dependencies needed on a fresh Debian/Ubuntu VM
# Run once before first deploy: sudo bash predeploy.sh
set -e

APP_USER="${1:-michaelphan}"
PROJECT_DIR="/opt/sms-api"

echo "=== SMS API Pre-deploy Setup ==="
echo "User: $APP_USER"
echo "Project: $PROJECT_DIR"
echo ""

# --- System packages ---
echo ">> Installing system packages..."
apt-get update -qq
apt-get install -y -qq git curl unzip

# --- Python (ensure 3.11+) ---
echo ">> Installing Python..."
apt-get install -y -qq python3 python3-venv

# --- uv (Python package manager) ---
echo ">> Installing uv..."
su - "$APP_USER" -c 'curl -LsSf https://astral.sh/uv/install.sh | sh' || true

# --- Bun (JS runtime) ---
echo ">> Installing bun..."
su - "$APP_USER" -c 'curl -fsSL https://bun.sh/install | bash' || true

# --- Project directory ---
echo ">> Setting up project directory..."
if [ ! -d "$PROJECT_DIR" ]; then
  mkdir -p "$PROJECT_DIR"
  chown "$APP_USER:$APP_USER" "$PROJECT_DIR"
  echo "  Clone repo: git clone <repo-url> $PROJECT_DIR"
fi

# --- passkey.conf ---
if [ ! -f "$PROJECT_DIR/passkey.conf" ]; then
  if [ -f "$PROJECT_DIR/passkey.conf.example" ]; then
    cp "$PROJECT_DIR/passkey.conf.example" "$PROJECT_DIR/passkey.conf"
    chown "$APP_USER:$APP_USER" "$PROJECT_DIR/passkey.conf"
    echo "  Created passkey.conf from example — edit with real keys!"
  fi
fi

# --- Python venv + deps ---
echo ">> Setting up Python venv..."
su - "$APP_USER" -c "
  export PATH=\"\$HOME/.local/bin:\$HOME/.cargo/bin:\$PATH\"
  cd $PROJECT_DIR
  uv venv .venv --python 3.13 2>/dev/null || uv venv .venv
  uv pip install -r requirements.txt --quiet
"

# --- Build frontend ---
echo ">> Building frontend..."
su - "$APP_USER" -c "
  export PATH=\"\$HOME/.bun/bin:\$PATH\"
  cd $PROJECT_DIR/frontend
  bun install
  bun run build
"

# --- Systemd: sms-api ---
echo ">> Creating sms-api systemd service..."
cat > /etc/systemd/system/sms-api.service <<EOF
[Unit]
Description=SMS API Service
After=network.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# --- Sudoers for deploy (no-password restart) ---
echo ">> Setting up sudoers for deploy..."
cat > /etc/sudoers.d/sms-api-deploy <<EOF
$APP_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart sms-api
$APP_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart cloudflared
$APP_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart smsd
$APP_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl status smsd
EOF
chmod 440 /etc/sudoers.d/sms-api-deploy

# --- Enable & start ---
echo ">> Enabling services..."
systemctl daemon-reload
systemctl enable sms-api
systemctl start sms-api || echo "  Warning: sms-api failed to start (check passkey.conf)"

echo ""
echo "=== Pre-deploy complete ==="
echo ""
echo "TODO:"
echo "  1. Edit $PROJECT_DIR/passkey.conf with real SECRET_KEY and ADMIN_KEY"
echo "  2. Setup cloudflared tunnel (see docs/deployment-guide.md)"
echo "  3. Setup GitHub self-hosted runner (see docs/deployment-guide.md section 4)"
echo "  4. Push to main → auto deploy"
