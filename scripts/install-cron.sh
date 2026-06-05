#!/bin/bash
# Job Hunter — Install cron jobs on VPS (Linux/Ubuntu paths)
# Run after setup-vps.sh
# Usage: bash scripts/install-cron.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$PROJECT_DIR/venv/bin/python"

echo "Installing cron jobs for Job Hunter..."
echo "Project: $PROJECT_DIR"

# Remove any old job-hunter cron entries
EXISTING=$(crontab -l 2>/dev/null | grep -v "Job-Hunter" | grep -v "job-hunter" || true)

NEW_CRON=$(cat <<EOF
$EXISTING
# Job Hunter — daily scans (EDT = UTC-4 in summer, UTC-5 in winter)
# 8am EDT = 12:00 UTC (summer) | adjust to 13:00 in winter
0 12 * * * /bin/bash $PROJECT_DIR/scripts/daily-scan.sh >> $PROJECT_DIR/logs/daily-scan.log 2>&1
0 16 * * * /bin/bash $PROJECT_DIR/scripts/daily-scan.sh >> $PROJECT_DIR/logs/daily-scan.log 2>&1
0 19 * * * /bin/bash $PROJECT_DIR/scripts/daily-scan.sh >> $PROJECT_DIR/logs/daily-scan.log 2>&1
# Job Hunter — instant watcher every 15min, 12:00–00:00 UTC (8am–8pm EDT)
*/15 12-23 * * * $PYTHON $PROJECT_DIR/scripts/watcher.py >> $PROJECT_DIR/logs/watcher.log 2>&1
EOF
)

echo "$NEW_CRON" | crontab -

echo "  ✓ Cron installed. Verify with: crontab -l"
crontab -l | grep "Job-Hunter"
