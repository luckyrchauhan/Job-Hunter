#!/bin/bash
# Install Job Hunter Telegram bot as a systemd service
# Usage: bash scripts/install-bot-service.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$PROJECT_DIR/venv/bin/python"
SERVICE_FILE="/etc/systemd/system/job-hunter-bot.service"

echo "Installing Job Hunter Telegram bot service..."

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Job Hunter Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON $PROJECT_DIR/scripts/telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_DIR/logs/bot.log
StandardError=append:$PROJECT_DIR/logs/bot.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable job-hunter-bot
systemctl start job-hunter-bot

echo "  ✓ Service installed and started"
echo ""
echo "Commands:"
echo "  systemctl status job-hunter-bot   — check status"
echo "  systemctl restart job-hunter-bot  — restart"
echo "  tail -f $PROJECT_DIR/logs/bot.log — view logs"
