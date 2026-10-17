#!/bin/bash
# MARCENZO Loan Bot — One-shot Ubuntu deploy
set -euo pipefail

APP_DIR="/root/marcenzo-loan-bot"
SERVICE_NAME="loan-bot"

echo "=== MARCENZO Loan Bot Deploy ==="

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: $APP_DIR not found. Extract/clone the project there first."
  exit 1
fi

cd "$APP_DIR"

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  if [ -f ".env.SERVER_TEMPLATE" ]; then
    cp .env.SERVER_TEMPLATE .env
    echo "Copied .env.SERVER_TEMPLATE → .env"
  else
    echo "WARNING: No .env found. Create one from .env.example"
  fi
fi

mkdir -p data logs media

cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=MARCENZO Loan Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}
Environment=PATH=${APP_DIR}/venv/bin
ExecStart=${APP_DIR}/venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}

echo ""
echo "=== Deploy complete ==="
echo "Status: systemctl status ${SERVICE_NAME}"
echo "Logs:   journalctl -u ${SERVICE_NAME} -f"
echo ""
systemctl status ${SERVICE_NAME} --no-pager || true
