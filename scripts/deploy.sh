#!/bin/bash
# Job Hunter — Pull latest code on VPS
# Usage: bash scripts/deploy.sh
# Run this whenever you push new code from your Mac

set -e
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "Deploying latest Job Hunter..."
git pull
venv/bin/pip install -r requirements.txt -q
echo "  ✓ Deploy done — $(git log -1 --format='%h %s')"
