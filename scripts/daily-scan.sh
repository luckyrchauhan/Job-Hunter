#!/bin/bash
# Job Hunter — Daily Scan Script
# Runs at 8:00 AM EDT via cron
# Cron entry: 0 8 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$PROJECT_DIR/logs/daily-scan.log"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/data/jobs-raw"

echo "========================================"
echo "Job Hunter Daily Scan — $TIMESTAMP EDT"
echo "========================================"

# Load environment
source "$PROJECT_DIR/.env" 2>/dev/null || { echo "ERROR: .env not found"; exit 1; }

# Validate required keys
if [ -z "$APIFY_API_TOKEN" ]; then
    echo "WARNING: APIFY_API_TOKEN not set — skipping Apify sources"
fi
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set — cannot score jobs"; exit 1
fi

cd "$PROJECT_DIR"

echo ""
echo "--- PHASE 1: SCRAPING ---"

# LinkedIn (Apify)
echo "[1/9] Scraping LinkedIn..."
python3 scripts/scrapers/scrape_linkedin.py && echo "     LinkedIn ✓" || echo "     LinkedIn FAILED"

# Indeed (Apify)
echo "[2/9] Scraping Indeed..."
python3 scripts/scrapers/scrape_indeed.py && echo "     Indeed ✓" || echo "     Indeed FAILED"

# Glassdoor (Apify)
echo "[3/9] Scraping Glassdoor..."
python3 scripts/scrapers/scrape_glassdoor.py && echo "     Glassdoor ✓" || echo "     Glassdoor FAILED"

# Wellfound (Playwright)
echo "[4/9] Scraping Wellfound..."
python3 scripts/scrapers/scrape_wellfound.py && echo "     Wellfound ✓" || echo "     Wellfound FAILED"

# YC Jobs (Playwright)
echo "[5/9] Scraping YC Jobs..."
python3 scripts/scrapers/scrape_yc.py && echo "     YC Jobs ✓" || echo "     YC Jobs FAILED"

# Levels.fyi
echo "[6/9] Scraping Levels.fyi..."
python3 scripts/scrapers/scrape_levels.py && echo "     Levels.fyi ✓" || echo "     Levels.fyi FAILED"

# Builtin
echo "[7/9] Scraping Builtin..."
python3 scripts/scrapers/scrape_builtin.py && echo "     Builtin ✓" || echo "     Builtin FAILED"

# Niche boards
echo "[8/9] Scraping Niche Boards..."
python3 scripts/scrapers/scrape_niche.py && echo "     Niche Boards ✓" || echo "     Niche Boards FAILED"

# Company direct (weekly only — runs on Mondays)
if [ "$(date +%u)" = "1" ]; then
    echo "[9/9] Scraping Company Career Pages (weekly)..."
    python3 scripts/scrapers/scrape_company_direct.py && echo "     Company Direct ✓" || echo "     Company Direct FAILED"
else
    echo "[9/9] Company Direct — skipped (runs Mondays only)"
fi

echo ""
echo "--- PHASE 2: SCORE & FILTER ---"
python3 scripts/score_jobs.py && echo "Scoring complete ✓" || echo "Scoring FAILED"

echo ""
echo "--- PHASE 3: NOTIFY ---"
python3 scripts/notify_telegram.py && echo "Telegram notification sent ✓" || echo "Notification FAILED"

echo ""
echo "--- PHASE 4: DEADLINE CHECK ---"
python3 scripts/deadline_check.py && echo "Deadline check complete ✓" || echo "Deadline check FAILED"

echo ""
echo "Scan complete — $(date +"%H:%M:%S")"
echo "========================================"
