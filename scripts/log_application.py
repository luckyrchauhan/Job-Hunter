#!/usr/bin/env python3
"""
M6 — Log Application
Writes a submitted application to data/applications.json
and regenerates outputs/tracker.xlsx.

Usage:
  python scripts/log_application.py --company "Stripe" --role "Senior PM" \
         --job-id "stripe-senior-pm-2026-05-25" --score 9 --visa confirmed \
         --apply-url "https://stripe.com/jobs/123" --outreach-contact "Jane Doe"
  
  python scripts/log_application.py --from-scored <job_id>   # pull from jobs-scored.json
  python scripts/log_application.py --list                    # show all logged applications
  python scripts/log_application.py --followups               # show overdue follow-ups
"""

import json
import re
import sys
import argparse
import subprocess
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

BASE_DIR  = Path(__file__).parent.parent
APPS_FILE = BASE_DIR / "data" / "applications.json"
SCORED    = BASE_DIR / "data" / "jobs-scored.json"

TODAY = date.today().isoformat()

SLACK_WEBHOOK = __import__("os").getenv("SLACK_WEBHOOK_URL", "")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def load_apps() -> list:
    if not APPS_FILE.exists():
        return []
    content = APPS_FILE.read_text().strip()
    if not content:
        return []
    return json.loads(content)


def save_apps(apps: list):
    with open(APPS_FILE, "w") as f:
        json.dump(apps, f, indent=2)


def log_application(app_record: dict, dry_run: bool = False) -> dict:
    """Add or update application record. Returns final record."""
    apps = load_apps()
    app_id = app_record["id"]

    # Upsert
    existing_idx = next((i for i, a in enumerate(apps) if a["id"] == app_id), None)
    if existing_idx is not None:
        apps[existing_idx].update(app_record)
        record = apps[existing_idx]
        action = "updated"
    else:
        apps.append(app_record)
        record = app_record
        action = "added"

    if not dry_run:
        save_apps(apps)
        print(f"✅ Application {action}: {record['company']} — {record['role']}")
        print(f"   Follow-up due: {record.get('follow_up_due', '—')}")
        print(f"   ID: {record['id']}")

        # Regenerate Excel
        try:
            result = subprocess.run(
                [sys.executable, str(BASE_DIR / "scripts" / "export-tracker.py")],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"   tracker.xlsx regenerated")
            else:
                print(f"   ⚠ tracker export failed: {result.stderr[:100]}")
        except Exception as e:
            print(f"   ⚠ tracker export error: {e}")

        # Slack notification
        if SLACK_WEBHOOK:
            _notify_slack_logged(record)
    else:
        print(f"[dry-run] Would {action}: {record['company']} — {record['role']}")

    return record


def _notify_slack_logged(record: dict):
    import urllib.request
    msg = (
        f"📝 *Application Logged*\n"
        f"*{record['company']}* — {record['role']}\n"
        f"Score: {record.get('score','?')} | Visa: {record.get('visa','?')}\n"
        f"Follow-up due: {record.get('follow_up_due','—')}"
    )
    payload = json.dumps({"text": msg}).encode()
    req = urllib.request.Request(
        SLACK_WEBHOOK, data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"  ⚠ Slack notify failed: {e}")


def show_followups():
    """Print applications with overdue or upcoming follow-ups."""
    apps = load_apps()
    today = date.today()
    soon  = (today + timedelta(days=3)).isoformat()

    overdue = []
    upcoming = []

    for a in apps:
        if a.get("status") not in ("applied", "outreach_sent", "interviewing"):
            continue
        due = a.get("follow_up_due", "")
        if not due:
            continue
        if due < TODAY:
            overdue.append(a)
        elif due <= soon:
            upcoming.append(a)

    if overdue:
        print(f"\n🔴 OVERDUE FOLLOW-UPS ({len(overdue)})")
        for a in sorted(overdue, key=lambda x: x.get("follow_up_due","")):
            print(f"  {a['company']:<25} {a.get('role','')[:30]:<32} due: {a['follow_up_due']}")

    if upcoming:
        print(f"\n🟡 DUE SOON ({len(upcoming)})")
        for a in sorted(upcoming, key=lambda x: x.get("follow_up_due","")):
            print(f"  {a['company']:<25} {a.get('role','')[:30]:<32} due: {a['follow_up_due']}")

    if not overdue and not upcoming:
        print("✅ No follow-ups overdue or due in the next 3 days")


def main():
    parser = argparse.ArgumentParser(description="Log an application to applications.json")
    parser.add_argument("--from-scored",  metavar="JOB_ID", help="Pull job data from jobs-scored.json")
    parser.add_argument("--company",      help="Company name")
    parser.add_argument("--role",         help="Role title")
    parser.add_argument("--job-id",       help="Unique job ID")
    parser.add_argument("--score",        type=float, default=0)
    parser.add_argument("--visa",         default="unknown")
    parser.add_argument("--apply-url",    default="")
    parser.add_argument("--salary",       default="")
    parser.add_argument("--urgency",      default="")
    parser.add_argument("--outreach-contact", default="")
    parser.add_argument("--outreach-sent", action="store_true")
    parser.add_argument("--notes",        default="")
    parser.add_argument("--applied-date", default=TODAY)
    parser.add_argument("--dry-run",      action="store_true")
    parser.add_argument("--list",         action="store_true", help="List all applications")
    parser.add_argument("--followups",    action="store_true", help="Show follow-ups due")
    args = parser.parse_args()

    if args.list:
        apps = load_apps()
        if not apps:
            print("No applications logged yet.")
            return
        print(f"\n{'Company':<25} {'Role':<35} {'Score':<6} {'Status':<18} {'Applied':<12} {'Follow-up'}")
        print("─" * 110)
        for a in sorted(apps, key=lambda x: x.get("applied_date",""), reverse=True):
            print(f"{a.get('company',''):<25} {a.get('role','')[:34]:<35} "
                  f"{str(a.get('score','')):<6} {a.get('status',''):<18} "
                  f"{a.get('applied_date',''):<12} {a.get('follow_up_due','')}")
        return

    if args.followups:
        show_followups()
        return

    # Build record from --from-scored or manual flags
    if args.from_scored:
        if not SCORED.exists():
            print("✗ data/jobs-scored.json not found")
            sys.exit(1)
        with open(SCORED) as f:
            jobs = json.load(f)
        job = next((j for j in jobs if j["id"] == args.from_scored), None)
        if not job:
            print(f"✗ Job ID not found: {args.from_scored}")
            sys.exit(1)
        company  = job.get("company", "")
        role     = job.get("title", "")
        job_id   = job["id"]
        score    = job.get("score", 0)
        visa     = job.get("visa_status", "unknown")
        apply_url = job.get("apply_url", "")
        salary   = job.get("salary_text", "")
        urgency  = job.get("urgency_label", "")
    else:
        if not args.company or not args.role:
            print("✗ --company and --role required (or use --from-scored <job_id>)")
            sys.exit(1)
        company   = args.company
        role      = args.role
        job_id    = args.job_id or f"{slug(company)}-{slug(role)}-{args.applied_date}"
        score     = args.score
        visa      = args.visa
        apply_url = args.apply_url
        salary    = args.salary
        urgency   = args.urgency

    applied_date  = args.applied_date
    follow_up_due = (date.fromisoformat(applied_date) + timedelta(days=7)).isoformat()

    record = {
        "id":               job_id,
        "company":          company,
        "role":             role,
        "apply_url":        apply_url,
        "score":            score,
        "urgency":          urgency,
        "visa":             visa,
        "salary_text":      salary,
        "status":           "applied",
        "applied_date":     applied_date,
        "follow_up_due":    follow_up_due,
        "outreach_contact": args.outreach_contact,
        "outreach_sent":    args.outreach_sent,
        "notes":            args.notes,
        "outcome":          None,
        "outcome_date":     None,
        "logged_at":        datetime.now(timezone.utc).isoformat(),
    }

    log_application(record, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
