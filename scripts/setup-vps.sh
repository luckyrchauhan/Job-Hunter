#!/bin/bash
# Job Hunter — VPS Bootstrap Script
# Run once on a fresh Ubuntu 22.04 VPS (Hostinger or any provider)
# Usage: bash setup-vps.sh
# After: copy .env, then run: bash scripts/install-cron.sh

set -e

REPO_URL="${1:-https://github.com/YOUR_USERNAME/YOUR_REPO.git}"
PROJECT_DIR="$HOME/Job-Hunter"

echo "========================================"
echo "Job Hunter — VPS Setup"
echo "Ubuntu 22.04 | 2GB RAM"
echo "========================================"

# --- System deps ---
echo ""
echo "[1/6] System packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3 python3-venv python3-pip \
    git curl wget unzip \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxcb1 libxkbcommon0 libx11-6 \
    libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2t64 \
    fonts-liberation xdg-utils
echo "  ✓ System packages installed"

# --- Clone repo ---
echo ""
echo "[2/6] Clone repo..."
if [ -d "$PROJECT_DIR" ]; then
    echo "  Dir exists — pulling latest..."
    cd "$PROJECT_DIR" && git pull
else
    git clone "$REPO_URL" "$PROJECT_DIR"
fi
cd "$PROJECT_DIR"
echo "  ✓ Repo ready at $PROJECT_DIR"

# --- Python venv ---
echo ""
echo "[3/6] Python venv + deps..."
python3 -m venv venv
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q
echo "  ✓ Python deps installed"

# --- Playwright browsers ---
echo ""
echo "[4/6] Playwright Chromium (~300MB)..."
venv/bin/playwright install chromium
venv/bin/playwright install-deps chromium
echo "  ✓ Playwright ready"

# --- Directories ---
echo ""
echo "[5/6] Data directories..."
mkdir -p logs data/jobs-raw outputs/resumes outputs/cover-letters outputs/outreach
chmod 755 scripts/*.sh scripts/*.py 2>/dev/null || true
echo "  ✓ Dirs ready"

# --- .env check ---
echo ""
echo "[6/6] Checking .env..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "  ⚠  .env NOT FOUND — copy it now:"
    echo "     From your Mac: scp .env user@YOUR_VPS_IP:$PROJECT_DIR/.env"
    echo "     Or create it:  nano $PROJECT_DIR/.env"
else
    echo "  ✓ .env found"
fi

echo ""
echo "========================================"
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Copy .env:   scp .env user@VPS_IP:$PROJECT_DIR/.env"
echo "  2. Install cron: bash $PROJECT_DIR/scripts/install-cron.sh"
echo "  3. Test scan:    bash $PROJECT_DIR/scripts/daily-scan.sh"
echo "========================================"
