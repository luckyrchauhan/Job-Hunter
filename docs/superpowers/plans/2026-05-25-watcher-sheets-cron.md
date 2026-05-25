# Watcher + Google Sheets + Multi-Cron Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real-time job watcher (fires instant Slack alert for score ≥ 8 + posted < 2hrs), replace tracker.xlsx with live Google Sheets sync, and update cron to run at 8am/12pm/3pm.

**Architecture:** Three independent additions — (1) `watcher.py` is a standalone polling script that does delta scraping + instant alerting, (2) `sync_sheets.py` replaces `export-tracker.py` as the tracker sync layer using Google Sheets API, (3) cron + shell updates wire everything together. Existing `daily-scan.sh`, `notify_slack.py`, and `export-tracker.py` are minimally touched.

**Tech Stack:** Python 3, `google-auth`, `gspread` (Sheets API wrapper), existing `notify_slack.py` patterns, bash cron, `.env` config.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/watcher.py` | **Create** | 15-min delta poller — scrapes new postings, scores, sends instant Slack alert if score ≥ 8 + posted < 2hrs |
| `scripts/sync_sheets.py` | **Create** | Syncs `applications.json` → Google Sheet after every run or status change |
| `scripts/daily-scan.sh` | **Modify** | Replace `export-tracker.py` call with `sync_sheets.py`; update header comment re: 3 cron times |
| `config/search-params.json` | **Modify** | Add `instant_alert_score_threshold` and `instant_alert_max_age_hours` keys |
| `.env.example` | **Modify** | Add `GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON`, remove Telegram keys |
| `requirements.txt` | **Modify** | Add `gspread`, `google-auth` |
| `CLAUDE.md` | **Modify** | Update cron schedule section, tracker reference |

---

## Task 1: Update config + env + requirements

**Files:**
- Modify: `config/search-params.json`
- Modify: `.env.example`
- Modify: `requirements.txt`

- [ ] **Step 1: Read current search-params.json**

```bash
cat config/search-params.json
```

- [ ] **Step 2: Add instant alert thresholds to search-params.json**

Add these keys to `config/search-params.json` (merge into existing JSON object):

```json
"instant_alert_score_threshold": 8,
"instant_alert_max_age_hours": 2,
"instant_alert_max_applicants": 50,
"watcher_poll_interval_minutes": 15,
"watcher_active_hours_start": 8,
"watcher_active_hours_end": 20
```

- [ ] **Step 3: Update .env.example — swap Telegram for Slack + Google**

Replace the entire `.env.example` with:

```bash
# Claude API
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Apify (job scraping)
APIFY_API_TOKEN=your_apify_token_here

# Slack notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/your/webhook/url

# Google Sheets tracker
# Sheet ID from the URL: https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit
GOOGLE_SHEET_ID=your_google_sheet_id_here
# Path to service account JSON file (downloaded from Google Cloud Console)
GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/your/service-account.json

# LinkedIn (optional - for direct scraping)
LINKEDIN_EMAIL=your_linkedin_email_here
LINKEDIN_PASSWORD=your_linkedin_password_here

# H1B data sources (no keys needed — public scraping)
# myvisajobs.com, h1bdata.info, h1bgrader.com, h1bdatabase.com, h1bmetrics.com, dol.gov
```

- [ ] **Step 4: Add Google deps to requirements.txt**

```bash
echo "gspread>=6.0.0" >> requirements.txt
echo "google-auth>=2.0.0" >> requirements.txt
```

- [ ] **Step 5: Commit**

```bash
git add config/search-params.json .env.example requirements.txt
git commit -m "config: add instant alert thresholds + Google Sheets env vars"
```

---

## Task 2: Create sync_sheets.py — Google Sheets live tracker

**Files:**
- Create: `scripts/sync_sheets.py`

- [ ] **Step 1: Write sync_sheets.py**

```python
#!/usr/bin/env python3
"""
Google Sheets Live Tracker Sync
Reads:  data/applications.json
Syncs:  Google Sheet (tab: "Applications" — always current full view)
        Google Sheet (tab: YYYY-MM-DD — daily snapshot, appended once per day)
        Google Sheet (tab: "Summary" — pipeline counts)

Env:
  GOOGLE_SHEET_ID               — spreadsheet ID from URL
  GOOGLE_SERVICE_ACCOUNT_JSON   — path to service account .json file

Usage:
  python scripts/sync_sheets.py
  python scripts/sync_sheets.py --dry-run   # print rows, don't write
"""

import json
import os
import sys
import argparse
from datetime import date, datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
APPS_FILE = BASE_DIR / "data" / "applications.json"
TODAY = date.today().isoformat()

SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
SA_JSON  = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

COLUMNS = [
    "Company", "Role", "Score", "Visa", "Status",
    "Applied Date", "Follow-up Due", "Urgency", "Salary",
    "Outreach Contact", "Outreach Sent", "Apply URL", "Notes", "Outcome",
]


def load_applications() -> list:
    if not APPS_FILE.exists():
        return []
    content = APPS_FILE.read_text().strip()
    if not content:
        return []
    return json.loads(content)


def app_to_row(app: dict) -> list:
    return [
        app.get("company", ""),
        app.get("role", ""),
        app.get("score", ""),
        app.get("visa", ""),
        app.get("status", ""),
        app.get("applied_date", ""),
        app.get("follow_up_due", ""),
        app.get("urgency", ""),
        app.get("salary_text", ""),
        app.get("outreach_contact", ""),
        "Yes" if app.get("outreach_sent") else "No",
        app.get("apply_url", ""),
        app.get("notes", ""),
        app.get("outcome", ""),
    ]


def get_client():
    """Return authenticated gspread client."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("✗ gspread not installed — run: pip install gspread google-auth")
        sys.exit(1)

    if not SHEET_ID:
        print("✗ GOOGLE_SHEET_ID not set in .env")
        sys.exit(1)
    if not SA_JSON:
        print("✗ GOOGLE_SERVICE_ACCOUNT_JSON not set in .env")
        sys.exit(1)
    if not Path(SA_JSON).exists():
        print(f"✗ Service account file not found: {SA_JSON}")
        sys.exit(1)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(SA_JSON, scopes=scopes)
    return gspread.authorize(creds)


def sort_apps(apps: list) -> list:
    STATUS_ORDER = {
        "offer": 0, "interviewing": 1, "applied": 2,
        "outreach_sent": 2, "ready_to_apply": 3,
        "stale": 4, "rejected": 5, "withdrawn": 6,
    }
    return sorted(
        apps,
        key=lambda x: (STATUS_ORDER.get(x.get("status", ""), 9), -(x.get("score") or 0))
    )


def sync_tab_full(ws, apps: list):
    """Overwrite a tab with header + all rows. Preserves user-added columns beyond col 14."""
    rows = [COLUMNS] + [app_to_row(a) for a in sort_apps(apps)]
    # Only update columns A–N (our 14 columns) — don't touch user columns O+
    ws.update(f"A1:N{len(rows)}", rows)
    print(f"  ✓ Tab '{ws.title}' — {len(apps)} rows written")


def ensure_daily_tab(spreadsheet, tab_name: str, apps: list):
    """Add dated snapshot tab if it doesn't exist yet today."""
    import gspread
    try:
        ws = spreadsheet.worksheet(tab_name)
        print(f"  ⚡ Tab '{tab_name}' already exists — skipping snapshot")
        return
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=tab_name, rows=500, cols=len(COLUMNS))

    rows = [COLUMNS] + [app_to_row(a) for a in sort_apps(apps)]
    ws.update(f"A1:N{len(rows)}", rows)
    print(f"  ✓ Snapshot tab '{tab_name}' created — {len(apps)} rows")


def sync_summary_tab(spreadsheet, apps: list):
    """Overwrite Summary tab with pipeline counts + overdue follow-ups."""
    from collections import Counter
    import gspread

    try:
        ws = spreadsheet.worksheet("Summary")
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="Summary", rows=50, cols=3)

    status_counts = Counter(a.get("status", "unknown") for a in apps)
    rows = [
        ["PIPELINE SUMMARY", "", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
        ["Total Applications", len(apps), ""],
        ["", "", ""],
        ["Status", "Count", ""],
    ]
    for s in ["applied", "outreach_sent", "interviewing", "offer",
              "rejected", "stale", "withdrawn", "ready_to_apply"]:
        rows.append([s.replace("_", " ").title(), status_counts.get(s, 0), ""])

    rows += [["", "", ""], ["FOLLOW-UPS OVERDUE", "", ""]]
    due = [a for a in apps
           if a.get("follow_up_due", "") < TODAY
           and a.get("status") in ("applied", "outreach_sent", "interviewing")]
    if due:
        for a in due:
            rows.append([f"{a.get('company')} — {a.get('role','')[:30]}", a.get("follow_up_due",""), ""])
    else:
        rows.append(["None overdue ✅", "", ""])

    ws.update("A1:C" + str(len(rows)), rows)
    print(f"  ✓ Summary tab updated")


def upsert_job_row(spreadsheet, job: dict):
    """
    Add or update a single scored job row in the 'Scored Jobs' tab.
    Used by watcher.py for instant-alert jobs.
    """
    import gspread

    SCORED_COLS = ["ID", "Company", "Role", "Score", "Urgency", "Visa",
                   "Salary", "Posted", "Applicants", "Apply URL", "Alerted At"]

    try:
        ws = spreadsheet.worksheet("Scored Jobs")
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="Scored Jobs", rows=1000, cols=len(SCORED_COLS))
        ws.update("A1:K1", [SCORED_COLS])

    job_id = job.get("id", "")
    # Find existing row by ID (col A)
    col_a = ws.col_values(1)
    if job_id in col_a:
        row_num = col_a.index(job_id) + 1
    else:
        row_num = len(col_a) + 1

    row = [
        job_id,
        job.get("company", ""),
        job.get("title", ""),
        job.get("score", ""),
        job.get("urgency", ""),
        job.get("visa", ""),
        job.get("salary_text", ""),
        job.get("posted_at", ""),
        job.get("applicant_count", ""),
        job.get("apply_url", ""),
        datetime.now().strftime("%Y-%m-%d %H:%M"),
    ]
    ws.update(f"A{row_num}:K{row_num}", [row])


def main():
    parser = argparse.ArgumentParser(description="Sync applications.json → Google Sheets")
    parser.add_argument("--dry-run", action="store_true", help="Print rows without writing")
    args = parser.parse_args()

    apps = load_applications()
    print(f"Loaded {len(apps)} application(s) from data/applications.json")

    if args.dry_run:
        print("\n[DRY RUN] Rows that would be written:")
        for a in sort_apps(apps):
            print(" ", app_to_row(a))
        return

    client = get_client()
    spreadsheet = client.open_by_key(SHEET_ID)

    print(f"Connected to sheet: {spreadsheet.title}")

    # 1. Full "Applications" tab
    try:
        import gspread
        ws_all = spreadsheet.worksheet("Applications")
        ws_all.clear()
    except Exception:
        ws_all = spreadsheet.add_worksheet(title="Applications", rows=1000, cols=len(COLUMNS))
    sync_tab_full(ws_all, apps)

    # 2. Daily snapshot tab (only created once per day)
    ensure_daily_tab(spreadsheet, TODAY, apps)

    # 3. Summary tab
    sync_summary_tab(spreadsheet, apps)

    print(f"\n✅ Google Sheets synced → https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/sync_sheets.py
```

- [ ] **Step 3: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('scripts/sync_sheets.py').read()); print('✓ syntax ok')"
```

Expected: `✓ syntax ok`

- [ ] **Step 4: Test dry run (no Google creds needed)**

```bash
python3 scripts/sync_sheets.py --dry-run
```

Expected: `Loaded 0 application(s)` or rows printed, NO crash, no Google API called.

- [ ] **Step 5: Commit**

```bash
git add scripts/sync_sheets.py
git commit -m "feat: add sync_sheets.py — live Google Sheets tracker sync"
```

---

## Task 3: Create watcher.py — instant alert poller

**Files:**
- Create: `scripts/watcher.py`

- [ ] **Step 1: Write watcher.py**

```python
#!/usr/bin/env python3
"""
Job Hunter — Instant Alert Watcher
Polls every 15 minutes (8am–8pm EDT) for new high-match jobs.
Sends immediate Slack alert for: score >= 8 AND posted < 2hrs AND applicants < 50.

Runs independently from daily-scan.sh — does NOT do full scrape.
Uses lightweight endpoints only (RemoteOK RSS, Himalayas API, YC JSON API).

Usage:
  python scripts/watcher.py          # single poll cycle (run via cron */15)
  python scripts/watcher.py --once   # same as above, explicit
  python scripts/watcher.py --test   # send test Slack alert + exit

Cron entry (every 15min, 8am–8pm):
  */15 8-20 * * * /path/to/venv/bin/python /path/to/scripts/watcher.py
"""

import json
import os
import sys
import time
import hashlib
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SEEN_FILE    = BASE_DIR / "data" / "watcher-seen.json"
SCORED_FILE  = BASE_DIR / "data" / "jobs-scored.json"
PARAMS_FILE  = BASE_DIR / "config" / "search-params.json"

SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "")

# ── Load config ───────────────────────────────────────────────────────────────

def load_params() -> dict:
    if PARAMS_FILE.exists():
        return json.loads(PARAMS_FILE.read_text())
    return {}

# ── Seen-IDs cache (prevent duplicate alerts) ─────────────────────────────────

def load_seen() -> set:
    if SEEN_FILE.exists():
        data = json.loads(SEEN_FILE.read_text())
        return set(data.get("ids", []))
    return set()

def save_seen(ids: set):
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Trim to last 500 to avoid unbounded growth
    trimmed = list(ids)[-500:]
    SEEN_FILE.write_text(json.dumps({"ids": trimmed}, indent=2))

# ── Slack ─────────────────────────────────────────────────────────────────────

def send_slack(payload: dict) -> bool:
    if not SLACK_WEBHOOK:
        print("⚠ SLACK_WEBHOOK_URL not set — Slack alert skipped")
        return False
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK, data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = resp.status == 200
            if ok:
                print("  ✓ Slack alert sent")
            return ok
    except Exception as e:
        print(f"  ✗ Slack error: {e}")
        return False


def build_instant_alert(job: dict) -> dict:
    urgency_emoji = {
        "apply-now-critical": "🔴🔴",
        "apply-now-hot":      "🔴",
        "apply-now-today":    "🟠",
    }.get(job.get("urgency", ""), "⚡")

    score  = job.get("score", "?")
    title  = job.get("title", "Unknown Role")
    company = job.get("company", "Unknown")
    posted  = job.get("posted_text", job.get("posted_at", "recently"))
    salary  = job.get("salary_text", "Not listed")
    visa    = job.get("visa", "unclear")
    url     = job.get("apply_url", job.get("url", ""))
    source  = job.get("source", "")

    visa_icon = {"confirmed": "✅", "likely": "🟡", "unclear": "❓"}.get(visa, "❓")

    return {
        "text": f"{urgency_emoji} *INSTANT ALERT — Score: {score}/10*",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{urgency_emoji} *INSTANT ALERT — Score: {score}/10*\n"
                        f"*Role:* {title}\n"
                        f"*Company:* {company}\n"
                        f"*Posted:* {posted}\n"
                        f"*Salary:* {salary}\n"
                        f"*Visa:* {visa_icon} {visa.title()}\n"
                        f"*Source:* {source}\n"
                        f"*Apply:* <{url}|Open JD>"
                    )
                }
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"⚡ Watcher fired at {datetime.now().strftime('%H:%M')} EDT"}]
            }
        ]
    }

# ── Scoring (lightweight — reuse score_jobs.py logic) ─────────────────────────

def quick_score(job: dict, params: dict) -> int:
    """
    Fast heuristic score 1–10 without Claude API.
    Used by watcher to avoid API cost on every 15-min poll.
    For confirmed high-score jobs (≥8), the daily scan will do full AI scoring.
    """
    score = 5  # baseline
    title = (job.get("title", "") + " " + job.get("description", "")).lower()

    # Role title match
    pm_titles = ["product manager", "senior pm", "principal pm", "director of product",
                 "head of product", "apm", "associate pm", "platform pm", "ai pm"]
    if any(t in title for t in pm_titles):
        score += 2

    # AI/LLM signal
    if any(k in title for k in ["ai", "llm", "generative", "machine learning", "ml"]):
        score += 1.5

    # Enterprise / platform signal
    if any(k in title for k in ["enterprise", "platform", "saas", "b2b"]):
        score += 1

    # Negative signals
    if any(k in title for k in ["intern", "junior", "entry level", "associate"]):
        score -= 2
    if any(k in title for k in ["marketing", "sales", "hardware", "embedded"]):
        score -= 3

    return min(10, max(1, round(score)))


def is_recent(job: dict, max_hours: int) -> bool:
    """Return True if job posted within max_hours."""
    posted = job.get("posted_at", "")
    if not posted:
        return True  # unknown → assume recent, let score gate it

    try:
        # Handle ISO format: "2026-05-25T09:30:00Z" or "2026-05-25T09:30:00+00:00"
        if posted.endswith("Z"):
            posted = posted[:-1] + "+00:00"
        dt = datetime.fromisoformat(posted)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - dt
        return age <= timedelta(hours=max_hours)
    except (ValueError, TypeError):
        return True  # parse failure → assume recent


def make_job_id(job: dict) -> str:
    """Stable ID from URL or company+title hash."""
    url = job.get("apply_url", job.get("url", ""))
    if url:
        return hashlib.md5(url.encode()).hexdigest()[:12]
    raw = f"{job.get('company','')}-{job.get('title','')}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]

# ── Quick scrapers (delta only — fast, no Apify needed) ───────────────────────

def fetch_remoteok_new() -> list:
    """RemoteOK public JSON API — returns latest PM jobs."""
    try:
        url = "https://remoteok.com/api?tag=product-manager"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        jobs = []
        for item in data:
            if not isinstance(item, dict) or "position" not in item:
                continue
            title = item.get("position", "")
            if not any(t in title.lower() for t in ["product manager", "pm", "product"]):
                continue
            jobs.append({
                "id":        item.get("id", ""),
                "title":     title,
                "company":   item.get("company", ""),
                "apply_url": item.get("url", f"https://remoteok.com/l/{item.get('id','')}"),
                "posted_at": item.get("date", ""),
                "salary_text": f"${item.get('salary_min','')}–${item.get('salary_max','')}" if item.get("salary_min") else "",
                "source":    "RemoteOK",
                "description": " ".join(item.get("tags", [])),
            })
        return jobs
    except Exception as e:
        print(f"  ⚠ RemoteOK fetch failed: {e}")
        return []


def fetch_himalayas_new() -> list:
    """Himalayas public API — PM roles, remote only."""
    try:
        url = "https://himalayas.app/jobs/api?q=product+manager&limit=20&remoteOnly=true"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        jobs = []
        for item in data.get("jobs", []):
            jobs.append({
                "id":        item.get("id", ""),
                "title":     item.get("title", ""),
                "company":   item.get("company", {}).get("name", ""),
                "apply_url": item.get("applicationLink", item.get("url", "")),
                "posted_at": item.get("publishedAt", ""),
                "salary_text": item.get("salaryRange", ""),
                "source":    "Himalayas",
                "description": item.get("description", "")[:500],
            })
        return jobs
    except Exception as e:
        print(f"  ⚠ Himalayas fetch failed: {e}")
        return []


def fetch_yc_new() -> list:
    """YC Work at a Startup — PM roles."""
    try:
        url = "https://api.workatastartup.com/jobs?query=product+manager&remote=true&limit=20"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        jobs = []
        for item in data.get("jobs", []):
            jobs.append({
                "id":        str(item.get("id", "")),
                "title":     item.get("title", ""),
                "company":   item.get("company", {}).get("name", ""),
                "apply_url": f"https://www.workatastartup.com/jobs/{item.get('id','')}",
                "posted_at": item.get("created_at", ""),
                "salary_text": "",
                "source":    "YC",
                "description": item.get("description", "")[:500],
            })
        return jobs
    except Exception as e:
        print(f"  ⚠ YC fetch failed: {e}")
        return []

# ── Main poll cycle ───────────────────────────────────────────────────────────

def poll(params: dict, dry_run: bool = False) -> int:
    """
    Run one poll cycle. Returns count of instant alerts fired.
    """
    score_threshold  = params.get("instant_alert_score_threshold", 8)
    max_age_hours    = params.get("instant_alert_max_age_hours", 2)
    max_applicants   = params.get("instant_alert_max_applicants", 50)

    seen = load_seen()
    alerts_fired = 0

    print(f"\n[Watcher] {datetime.now().strftime('%Y-%m-%d %H:%M')} — polling delta sources...")

    all_jobs = []
    all_jobs += fetch_remoteok_new()
    all_jobs += fetch_himalayas_new()
    all_jobs += fetch_yc_new()

    print(f"  Fetched {len(all_jobs)} raw jobs from delta sources")

    new_jobs = []
    for job in all_jobs:
        jid = make_job_id(job)
        job["id"] = jid
        if jid not in seen:
            new_jobs.append(job)

    print(f"  {len(new_jobs)} unseen jobs")

    for job in new_jobs:
        seen.add(job["id"])

        # Applicant count gate
        applicants = job.get("applicant_count", 0) or 0
        if applicants >= max_applicants:
            print(f"  ⚡ {job['company']} — {job['title'][:40]} — skipped ({applicants} applicants)")
            continue

        # Recency gate
        if not is_recent(job, max_age_hours):
            continue

        # Score
        score = quick_score(job, params)
        job["score"] = score

        if score >= score_threshold:
            # Assign urgency
            posted = job.get("posted_at", "")
            if posted:
                try:
                    if posted.endswith("Z"):
                        posted = posted[:-1] + "+00:00"
                    dt = datetime.fromisoformat(posted)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    age_minutes = (datetime.now(timezone.utc) - dt).total_seconds() / 60
                    if age_minutes < 60:
                        job["urgency"] = "apply-now-critical"
                        job["posted_text"] = f"{int(age_minutes)} minutes ago"
                    else:
                        job["urgency"] = "apply-now-hot"
                        job["posted_text"] = f"{int(age_minutes/60)} hours ago"
                except Exception:
                    job["urgency"] = "apply-now-hot"
                    job["posted_text"] = "recently"
            else:
                job["urgency"] = "apply-now-hot"
                job["posted_text"] = "recently"

            print(f"  🔴 MATCH: {job['company']} — {job['title'][:40]} — score {score}/10")

            if not dry_run:
                payload = build_instant_alert(job)
                send_slack(payload)

                # Append to jobs-scored.json for daily-scan awareness
                _append_to_scored(job)

                # Sync to Google Sheets Scored Jobs tab
                _sync_job_to_sheets(job)

            alerts_fired += 1
        else:
            print(f"  · {job['company']} — {job['title'][:35]} — score {score}/10 (below threshold)")

    save_seen(seen)
    print(f"\n[Watcher] Done — {alerts_fired} instant alert(s) fired")
    return alerts_fired


def _append_to_scored(job: dict):
    """Append watcher-found job to jobs-scored.json so daily scan sees it."""
    scored = []
    if SCORED_FILE.exists():
        content = SCORED_FILE.read_text().strip()
        if content:
            scored = json.loads(content)
    # Don't duplicate
    existing_ids = {j.get("id") for j in scored}
    if job["id"] not in existing_ids:
        scored.append(job)
        SCORED_FILE.write_text(json.dumps(scored, indent=2))


def _sync_job_to_sheets(job: dict):
    """Best-effort sync to Google Sheets — skip silently if not configured."""
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
    sa_json  = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not sheet_id or not sa_json:
        return
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from sync_sheets import get_client, upsert_job_row
        client = get_client()
        spreadsheet = client.open_by_key(sheet_id)
        upsert_job_row(spreadsheet, job)
    except Exception as e:
        print(f"  ⚠ Sheets sync skipped: {e}")


def test_alert():
    """Send a test Slack message to verify webhook works."""
    payload = {
        "text": "⚡ *Job Hunter Watcher — Test Alert*",
        "blocks": [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "⚡ *Job Hunter Watcher — Test Alert*\nWatcher is configured correctly. Instant alerts will fire here for score ≥ 8 + posted < 2hrs."
            }
        }]
    }
    ok = send_slack(payload)
    if ok:
        print("✅ Test alert sent to Slack")
    else:
        print("✗ Test alert failed — check SLACK_WEBHOOK_URL in .env")


def main():
    # Load .env
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    parser = argparse.ArgumentParser(description="Job Hunter instant alert watcher")
    parser.add_argument("--once",    action="store_true", help="Run single poll cycle (default)")
    parser.add_argument("--test",    action="store_true", help="Send test Slack alert")
    parser.add_argument("--dry-run", action="store_true", help="Score + print matches, don't alert")
    args = parser.parse_args()

    if args.test:
        test_alert()
        return

    params = load_params()

    # Check active hours
    start_h = params.get("watcher_active_hours_start", 8)
    end_h   = params.get("watcher_active_hours_end", 20)
    now_h   = datetime.now().hour
    if not (start_h <= now_h < end_h) and not args.dry_run:
        print(f"[Watcher] Outside active hours ({start_h}–{end_h}h) — exiting")
        return

    poll(params, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/watcher.py
```

- [ ] **Step 3: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('scripts/watcher.py').read()); print('✓ syntax ok')"
```

Expected: `✓ syntax ok`

- [ ] **Step 4: Test dry run**

```bash
python3 scripts/watcher.py --dry-run
```

Expected: Fetches from RemoteOK/Himalayas/YC, prints scored jobs, no Slack call, no crash.

- [ ] **Step 5: Test Slack alert (requires SLACK_WEBHOOK_URL in .env)**

```bash
python3 scripts/watcher.py --test
```

Expected: `✅ Test alert sent to Slack` (or warning if webhook not set yet)

- [ ] **Step 6: Commit**

```bash
git add scripts/watcher.py
git commit -m "feat: add watcher.py — instant Slack alert for score>=8 jobs posted <2hrs"
```

---

## Task 4: Update daily-scan.sh + cron

**Files:**
- Modify: `scripts/daily-scan.sh`

- [ ] **Step 1: Update header comment and PHASE 5 in daily-scan.sh**

Replace the header comment block:

```bash
# Job Hunter — Daily Scan Script
# Runs at 8:00 AM EDT via cron
# Cron entry: 0 8 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1
```

With:

```bash
# Job Hunter — Scheduled Scan Script
# Runs at 8:00 AM, 12:00 PM, 3:00 PM EDT via cron
#
# Cron entries:
#   0  8 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1
#   0 12 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1
#   0 15 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1
#
# Instant watcher (every 15min, 8am–8pm):
#   */15 8-20 * * * /path/to/venv/bin/python /path/to/Job-Hunter/scripts/watcher.py >> /path/to/Job-Hunter/logs/watcher.log 2>&1
```

- [ ] **Step 2: Replace PHASE 5 export-tracker call with sync_sheets**

Find this block in `daily-scan.sh`:

```bash
echo ""
echo "--- PHASE 5: EXPORT TRACKER ---"
"$PYTHON" scripts/export-tracker.py && echo "  ✓ tracker.xlsx updated" || echo "  ✗ Tracker export FAILED"
```

Replace with:

```bash
echo ""
echo "--- PHASE 5: SYNC TRACKER ---"
"$PYTHON" scripts/sync_sheets.py && echo "  ✓ Google Sheets synced" || echo "  ✗ Sheets sync FAILED (check GOOGLE_SHEET_ID + GOOGLE_SERVICE_ACCOUNT_JSON)"
"$PYTHON" scripts/export-tracker.py && echo "  ✓ tracker.xlsx local backup updated" || echo "  ✗ Local xlsx export FAILED"
```

- [ ] **Step 3: Add missing env key warnings**

After the existing `SLACK_WEBHOOK_URL` warning line, add:

```bash
[ -z "$GOOGLE_SHEET_ID" ]              && echo "WARNING: GOOGLE_SHEET_ID not set — Sheets sync disabled"
[ -z "$GOOGLE_SERVICE_ACCOUNT_JSON" ]  && echo "WARNING: GOOGLE_SERVICE_ACCOUNT_JSON not set — Sheets sync disabled"
```

- [ ] **Step 4: Verify script syntax**

```bash
bash -n scripts/daily-scan.sh && echo "✓ shell syntax ok"
```

Expected: `✓ shell syntax ok`

- [ ] **Step 5: Commit**

```bash
git add scripts/daily-scan.sh
git commit -m "feat: update daily-scan.sh — 3x cron times + Google Sheets sync"
```

---

## Task 5: Update CLAUDE.md cron section

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update Cron Schedule section in CLAUDE.md**

Find:

```markdown
## Cron Schedule

- Daily scan: 8:00 AM EDT
- Deadline check: every 2 hours during business hours
```

Replace with:

```markdown
## Cron Schedule

- Scheduled scans: **8:00 AM, 12:00 PM, 3:00 PM EDT** (`daily-scan.sh`)
- Instant watcher: **every 15 minutes, 8am–8pm EDT** (`watcher.py`) — fires immediate Slack alert for score ≥ 8 + posted < 2hrs
- Deadline check: every 2 hours during business hours

### Cron entries to add (`crontab -e`):
```
0  8 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1
0 12 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1
0 15 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1
*/15 8-20 * * * /path/to/venv/bin/python /path/to/Job-Hunter/scripts/watcher.py >> /path/to/Job-Hunter/logs/watcher.log 2>&1
```
```

- [ ] **Step 2: Update tracker reference in CLAUDE.md**

Find:
```
- `outputs/tracker.xlsx` — auto-exported from applications.json
```

Replace with:
```
- `outputs/tracker.xlsx` — local Excel backup (auto-exported from applications.json)
- Google Sheets — live tracker, synced via `scripts/sync_sheets.py` after every scan (set `GOOGLE_SHEET_ID` in `.env`)
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md — cron schedule + Google Sheets tracker"
```

---

## Task 6: Install deps + end-to-end smoke test

**Files:** None (verification only)

- [ ] **Step 1: Install new deps**

```bash
source venv/bin/activate && pip install gspread google-auth
```

Expected: `Successfully installed gspread-X.X.X google-auth-X.X.X`

- [ ] **Step 2: Watcher dry-run smoke test**

```bash
python3 scripts/watcher.py --dry-run
```

Expected: Fetches jobs from RemoteOK/Himalayas/YC, prints scores, exits cleanly. No crash.

- [ ] **Step 3: Sheets dry-run smoke test**

```bash
python3 scripts/sync_sheets.py --dry-run
```

Expected: `Loaded 0 application(s)` + empty rows printed. No Google API called. No crash.

- [ ] **Step 4: Watcher test alert (requires SLACK_WEBHOOK_URL)**

```bash
python3 scripts/watcher.py --test
```

Expected: Slack message arrives in channel OR `⚠ SLACK_WEBHOOK_URL not set` warning.

- [ ] **Step 5: Final commit**

```bash
git add requirements.txt
git commit -m "chore: add gspread + google-auth to requirements.txt"
```

---

## Cron Setup Reference (for Lucky)

After merging, run `crontab -e` and add:

```cron
# Job Hunter — scheduled scans
0  8 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1
0 12 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1
0 15 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1

# Job Hunter — instant alert watcher (every 15min, 8am–8pm)
*/15 8-20 * * * /path/to/Job-Hunter/venv/bin/python /path/to/Job-Hunter/scripts/watcher.py >> /path/to/Job-Hunter/logs/watcher.log 2>&1
```

## Google Sheets Setup (for Lucky)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project → enable **Google Sheets API** + **Google Drive API**
3. Create **Service Account** → download JSON key
4. Set in `.env`: `GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/key.json`
5. Create a Google Sheet → copy the ID from URL
6. Set in `.env`: `GOOGLE_SHEET_ID=your_sheet_id`
7. **Share the sheet** with the service account email (editor access)
8. Run `python3 scripts/sync_sheets.py` to verify
