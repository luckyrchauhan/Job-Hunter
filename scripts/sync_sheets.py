#!/usr/bin/env python3
"""
Google Sheets Live Tracker Sync
Reads:  data/applications.json
Syncs:  Google Sheet (tab: "Applications" — always current full view)
        Google Sheet (tab: YYYY-MM-DD — daily snapshot, created once per day)
        Google Sheet (tab: "Summary" — pipeline counts + overdue follow-ups)
        Google Sheet (tab: "Scored Jobs" — jobs found by watcher.py)

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
    """Overwrite a tab with header + all rows (columns A–N only — preserves user columns O+)."""
    rows = [COLUMNS] + [app_to_row(a) for a in sort_apps(apps)]
    ws.update(rows, f"A1:N{len(rows)}")
    print(f"  ✓ Tab '{ws.title}' — {len(apps)} rows written")


def ensure_daily_tab(spreadsheet, tab_name: str, apps: list):
    """Add dated snapshot tab if it doesn't exist yet today."""
    try:
        import gspread
        ws = spreadsheet.worksheet(tab_name)
        print(f"  ⚡ Tab '{tab_name}' already exists — skipping snapshot")
        return
    except Exception:
        pass

    try:
        import gspread
        ws = spreadsheet.add_worksheet(title=tab_name, rows=500, cols=len(COLUMNS))
    except Exception as e:
        print(f"  ⚠ Could not create tab '{tab_name}': {e}")
        return

    rows = [COLUMNS] + [app_to_row(a) for a in sort_apps(apps)]
    ws.update(rows, f"A1:N{len(rows)}")
    print(f"  ✓ Snapshot tab '{tab_name}' created — {len(apps)} rows")


def sync_summary_tab(spreadsheet, apps: list):
    """Overwrite Summary tab with pipeline counts + overdue follow-ups."""
    from collections import Counter

    try:
        ws = spreadsheet.worksheet("Summary")
        ws.clear()
    except Exception:
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

    ws.update(rows, "A1:C" + str(len(rows)))
    print(f"  ✓ Summary tab updated")


def sync_scored_jobs_tab(spreadsheet):
    """Overwrite Scored Jobs tab with top 200 jobs from jobs-scored.json sorted by score."""
    scored_file = BASE_DIR / "data" / "jobs-scored.json"
    if not scored_file.exists():
        print("  ⚡ Scored Jobs — jobs-scored.json not found, skipping")
        return

    content = scored_file.read_text().strip()
    if not content:
        print("  ⚡ Scored Jobs — empty, skipping")
        return

    jobs = json.loads(content)
    jobs_sorted = sorted(jobs, key=lambda x: -(x.get("score") or 0))[:200]

    try:
        ws = spreadsheet.worksheet("Scored Jobs")
        ws.clear()
    except Exception:
        ws = spreadsheet.add_worksheet(title="Scored Jobs", rows=1000, cols=10)

    # Sort by priority_score desc, fallback to fit score
    jobs_sorted = sorted(
        jobs_sorted,
        key=lambda x: (-(x.get("priority_score") or 0), -(x.get("score") or 0))
    )

    COLS = [
        "Priority Score",   # A — cumulative apply rank (0–10)
        "Priority Band",    # B — 🔥/⚡/👀/📋
        "Fit Score",        # C — original fit score
        "Company",          # D
        "Role",             # E
        "H1B Sponsor",      # F — explicit/likely/unknown/no
        "Salary",           # G
        "Urgency",          # H
        "Posted",           # I
        "Location",         # J
        "Remote",           # K
        "Source",           # L
        "Apply URL",        # M
        "Status",           # N
        "Connections to Reach Out",  # O — filled when CSV loaded
        "Connection Email",          # P — filled when CSV loaded
        "Outreach Message",          # Q — filled when CSV loaded
    ]
    rows = [COLS]
    for j in jobs_sorted:
        visa_raw = j.get("visa_status_raw", "")
        if any(p in (j.get("description") or "").lower() for p in [
            "h1b sponsor", "h-1b sponsor", "will sponsor h1b", "h1b transfer",
            "visa sponsorship provided", "sponsoring h1b", "h1b visa sponsor",
        ]):
            h1b_display = "✅ Confirmed in JD"
        elif visa_raw in ["tier_1_heavy_sponsors", "tier_2_consistent_sponsors"]:
            h1b_display = "🟡 Likely (known sponsor)"
        elif visa_raw == "no_sponsorship":
            h1b_display = "❌ No Sponsorship"
        else:
            h1b_display = "❓ Unknown"

        rows.append([
            j.get("priority_score", ""),
            j.get("priority_band", ""),
            j.get("score", ""),
            j.get("company", ""),
            j.get("title", j.get("role", "")),
            h1b_display,
            j.get("salary_text", ""),
            j.get("urgency_label", j.get("urgency", "")),
            j.get("posted_at", j.get("posted_date", "")),
            j.get("location", ""),
            "✅ Remote" if j.get("remote") else "🏢 On-site",
            j.get("source", ""),
            j.get("apply_url", j.get("url", "")),
            j.get("status", "new"),
            j.get("connections_to_reach_out", ""),   # populated after CSV loaded
            j.get("connection_email", ""),            # populated after CSV loaded
            j.get("outreach_message", ""),            # populated after CSV loaded
        ])

    col_letter = "Q"
    ws.update(rows, f"A1:{col_letter}{len(rows)}")
    print(f"  ✓ Scored Jobs tab — {len(rows)-1} jobs written")


def upsert_job_row(spreadsheet, job: dict):
    """
    Add or update a single scored job row in the 'Scored Jobs' tab.
    Called by watcher.py for instant-alert jobs.
    """
    SCORED_COLS = [
        "Priority Score", "Priority Band", "Fit Score", "Company", "Role",
        "H1B Sponsor", "Salary", "Urgency", "Posted", "Location", "Remote",
        "Source", "Apply URL", "Status",
        "Connections to Reach Out", "Connection Email", "Outreach Message",
    ]

    try:
        ws = spreadsheet.worksheet("Scored Jobs")
    except Exception:
        ws = spreadsheet.add_worksheet(title="Scored Jobs", rows=1000, cols=len(SCORED_COLS))
        ws.update("A1:Q1", [SCORED_COLS])

    # Match on Apply URL (col M = index 12) to avoid duplicates
    apply_url = job.get("apply_url", job.get("url", ""))
    try:
        col_m = ws.col_values(13)
        if apply_url and apply_url in col_m:
            row_num = col_m.index(apply_url) + 1
        else:
            row_num = max(len(ws.col_values(1)) + 1, 2)
    except Exception:
        row_num = 2

    visa_raw = job.get("visa_status_raw", "")
    desc_lower = (job.get("description") or "").lower()
    if any(p in desc_lower for p in ["h1b sponsor", "h-1b sponsor", "will sponsor h1b"]):
        h1b_display = "✅ Confirmed in JD"
    elif visa_raw in ["tier_1_heavy_sponsors", "tier_2_consistent_sponsors"]:
        h1b_display = "🟡 Likely (known sponsor)"
    elif visa_raw == "no_sponsorship":
        h1b_display = "❌ No Sponsorship"
    else:
        h1b_display = "❓ Unknown"

    row = [
        job.get("priority_score", ""),
        job.get("priority_band", ""),
        job.get("score", ""),
        job.get("company", ""),
        job.get("title", ""),
        h1b_display,
        job.get("salary_text", ""),
        job.get("urgency_label", job.get("urgency", "")),
        job.get("posted_at", ""),
        job.get("location", ""),
        "✅ Remote" if job.get("remote") else "🏢 On-site",
        job.get("source", ""),
        apply_url,
        job.get("status", "new"),
        job.get("connections_to_reach_out", ""),
        job.get("connection_email", ""),
        job.get("outreach_message", ""),
    ]
    ws.update(f"A{row_num}:Q{row_num}", [row])
    print(f"  ✓ Scored Jobs tab — row {row_num} upserted ({job.get('company')} — {job.get('title','')})")


def main():
    # Load .env if present
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    # Re-read after env load
    global SHEET_ID, SA_JSON
    SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
    SA_JSON  = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

    parser = argparse.ArgumentParser(description="Sync applications.json → Google Sheets")
    parser.add_argument("--dry-run", action="store_true", help="Print rows without writing to Sheets")
    args = parser.parse_args()

    apps = load_applications()
    print(f"Loaded {len(apps)} application(s) from data/applications.json")

    if args.dry_run:
        print("\n[DRY RUN] Rows that would be written to 'Applications' tab:")
        print(f"  Header: {COLUMNS}")
        for a in sort_apps(apps):
            print(" ", app_to_row(a))
        print("\n[DRY RUN] No data written to Google Sheets.")
        return

    client = get_client()
    spreadsheet = client.open_by_key(SHEET_ID)
    print(f"Connected: {spreadsheet.title}")

    # 1. Full "Applications" tab — always current
    try:
        ws_all = spreadsheet.worksheet("Applications")
        ws_all.clear()
    except Exception:
        ws_all = spreadsheet.add_worksheet(title="Applications", rows=1000, cols=len(COLUMNS))
    sync_tab_full(ws_all, apps)

    # 2. Daily snapshot tab — created once per day, not overwritten
    ensure_daily_tab(spreadsheet, TODAY, apps)

    # 3. Summary tab
    sync_summary_tab(spreadsheet, apps)

    # 4. Scored Jobs tab — all scored jobs from jobs-scored.json
    sync_scored_jobs_tab(spreadsheet)

    print(f"\n✅ Google Sheets synced → https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")


if __name__ == "__main__":
    main()
