#!/bin/bash
# Job Hunter — Scheduled Scan Script
# Runs at 8:00 AM, 12:00 PM, 3:00 PM EDT via cron
#
# Cron entries (replace /path/to with your actual path):
#   0  8 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1
#   0 12 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1
#   0 15 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1
#
# Instant watcher (every 15min, 8am–8pm) — fires alerts WITHOUT waiting for this script:
#   */15 8-20 * * * /path/to/venv/bin/python /path/to/Job-Hunter/scripts/watcher.py >> /path/to/Job-Hunter/logs/watcher.log 2>&1

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$PROJECT_DIR/venv/bin/python"
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/data/jobs-raw"
mkdir -p "$PROJECT_DIR/outputs/resumes"
mkdir -p "$PROJECT_DIR/outputs/cover-letters"
mkdir -p "$PROJECT_DIR/outputs/outreach"

echo "========================================"
echo "Job Hunter Daily Scan — $TIMESTAMP EDT"
echo "========================================"

# Load environment
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a; source "$PROJECT_DIR/.env"; set +a
else
    echo "ERROR: .env not found"; exit 1
fi

# Validate venv
if [ ! -f "$PYTHON" ]; then
    echo "ERROR: venv not found at $PROJECT_DIR/venv — run: python3 -m venv venv && pip install -r requirements.txt"
    exit 1
fi

# Warn on missing keys (non-fatal — scrapers degrade gracefully)
[ -z "$APIFY_API_TOKEN" ]    && echo "WARNING: APIFY_API_TOKEN not set — Apify scrapers will skip"
[ -z "$ANTHROPIC_API_KEY" ]  && echo "WARNING: ANTHROPIC_API_KEY not set — AI drafting will use templates"
[ -z "$SLACK_WEBHOOK_URL" ]             && echo "WARNING: SLACK_WEBHOOK_URL not set — Slack alerts disabled"
[ -z "$GOOGLE_SHEET_ID" ]               && echo "WARNING: GOOGLE_SHEET_ID not set — Sheets sync disabled"
[ -z "$GOOGLE_SERVICE_ACCOUNT_JSON" ]   && echo "WARNING: GOOGLE_SERVICE_ACCOUNT_JSON not set — Sheets sync disabled"

cd "$PROJECT_DIR"

echo ""
echo "--- PHASE 1: SCRAPING ---"

run_scraper() {
    local name="$1"
    local script="$2"
    if [ -f "$script" ]; then
        echo "  Scraping $name..."
        "$PYTHON" "$script" && echo "  ✓ $name" || echo "  ✗ $name FAILED (continuing)"
    else
        echo "  ⚠ $name — script not found: $script (skipping)"
    fi
}

run_scraper "Hiring Cafe"    "scripts/scrapers/scrape_hiring_cafe.py"
run_scraper "Indeed"         "scripts/scrapers/scrape_indeed.py"
run_scraper "RemoteOK"       "scripts/scrapers/scrape_remoteok.py"
run_scraper "Himalayas"      "scripts/scrapers/scrape_himalayas.py"
run_scraper "YC Jobs"        "scripts/scrapers/scrape_yc.py"
run_scraper "LinkedIn"       "scripts/scrapers/scrape_linkedin.py"
run_scraper "Glassdoor"      "scripts/scrapers/scrape_glassdoor.py"
run_scraper "Wellfound"      "scripts/scrapers/scrape_wellfound.py"
run_scraper "Builtin"        "scripts/scrapers/scrape_builtin.py"
run_scraper "Dice"           "scripts/scrapers/scrape_dice.py"
run_scraper "Monster"        "scripts/scrapers/scrape_monster.py"
run_scraper "Niche Boards"   "scripts/scrapers/scrape_niche.py"
run_scraper "Greenhouse+Lever" "scripts/scrapers/scrape_greenhouse.py"
run_scraper "ZipRecruiter"   "scripts/scrapers/scrape_ziprecruiter.py"

# Google Jobs — SerpAPI fallback limited to 100/mo free tier
# Only run at 8am scan (hour 8) to conserve: 2 queries/day × 30 days = 60/month
CURRENT_HOUR=$(date +%H)
if [ "$CURRENT_HOUR" = "08" ] || [ "$CURRENT_HOUR" = "07" ]; then
    run_scraper "Google Jobs" "scripts/scrapers/scrape_google_jobs.py"
else
    echo "  ⚡ Google Jobs — morning scan only (SerpAPI 100/mo limit). Skipping."
fi

run_scraper "AI Jobs + Otta" "scripts/scrapers/scrape_aijobs.py"

# Company direct — weekly only (Mondays)
if [ "$(date +%u)" = "1" ]; then
    run_scraper "Company Career Pages" "scripts/scrapers/scrape_company_direct.py"
else
    echo "  ⚡ Company Direct — runs Mondays only (skipping)"
fi

# Fortune 500 — weekly only (Saturdays, day 6)
if [ "$(date +%u)" = "6" ]; then
    run_scraper "Fortune 500 Career Pages" "scripts/scrapers/scrape_fortune500.py"
else
    echo "  ⚡ Fortune 500 — runs Saturdays only (skipping)"
fi

echo ""
echo "--- PHASE 1b: ENRICH LINKEDIN (Firecrawl — disabled: LinkedIn blocks Firecrawl) ---"
echo "  ⚡ LinkedIn Firecrawl enrichment skipped — 0% success rate, saves 20 credits/scan"

echo ""
echo "--- PHASE 2: SCORE & FILTER ---"
"$PYTHON" scripts/score_jobs.py && echo "  ✓ Scoring complete" || echo "  ✗ Scoring FAILED"

echo ""
echo "--- PHASE 2b: MATCH CONNECTIONS ---"
if [ -f "$PROJECT_DIR/data/connections.csv" ]; then
    "$PYTHON" scripts/match_connections.py && echo "  ✓ Connections matched" || echo "  ✗ Connection match FAILED (continuing)"
else
    echo "  ⚡ data/connections.csv not found — skipping connection matching"
fi

echo ""
echo "--- PHASE 3: NOTIFY (Slack alerts) ---"
"$PYTHON" scripts/notify_slack.py && echo "  ✓ Alerts sent" || echo "  ✗ Slack alerts FAILED"

echo ""
echo "--- PHASE 4: DEADLINE CHECK ---"
"$PYTHON" scripts/deadline-check.py && echo "  ✓ Deadline check done" || echo "  ✗ Deadline check FAILED"

echo ""
echo "--- PHASE 5: SYNC TRACKER ---"
"$PYTHON" scripts/sync_sheets.py && echo "  ✓ Google Sheets synced" || echo "  ✗ Sheets sync FAILED (check GOOGLE_SHEET_ID + GOOGLE_SERVICE_ACCOUNT_JSON in .env)"
"$PYTHON" scripts/export-tracker.py && echo "  ✓ tracker.xlsx local backup updated" || echo "  ✗ Local xlsx export FAILED"

echo ""
echo "Scan complete — $(date +"%H:%M:%S")"
echo "========================================"
