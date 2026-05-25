#!/usr/bin/env python3
"""
Daily Status — 11pm Slack digest
Reads: data/applications.json, data/jobs-scored.json
Sends: Daily progress summary to Slack

Covers:
  - Pipeline stats (applied, interviewing, offers, follow-ups due)
  - Today's new jobs found
  - Overdue follow-ups
  - Wins / milestones

Usage:
  python scripts/daily_status.py           # send tonight's digest
  python scripts/daily_status.py --dry-run # preview without sending
"""

import json
import os
import sys
import urllib.request
import argparse
from collections import Counter
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

BASE_DIR    = Path(__file__).parent.parent
APPS_FILE   = BASE_DIR / "data" / "applications.json"
SCORED_FILE = BASE_DIR / "data" / "jobs-scored.json"

WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
TODAY       = date.today().isoformat()
TOMORROW    = (date.today() + timedelta(days=1)).isoformat()


def load_json(path: Path, default):
    if not path.exists():
        return default
    content = path.read_text().strip()
    if not content:
        return default
    return json.loads(content)


def send_slack(payload: dict) -> bool:
    if not WEBHOOK_URL:
        print("❌ SLACK_WEBHOOK_URL not set in .env")
        return False
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        WEBHOOK_URL, data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception as e:
        print(f"❌ Slack error: {e}")
        return False


def build_digest(apps: list, scored_jobs: list) -> dict:
    """Build the full nightly digest payload."""

    # ── Pipeline stats ────────────────────────────────────────────────────────
    status_counts = Counter(a.get("status", "unknown") for a in apps)
    total         = len(apps)
    applied       = status_counts.get("applied", 0) + status_counts.get("outreach_sent", 0)
    interviewing  = status_counts.get("interviewing", 0)
    offers        = status_counts.get("offer", 0)
    rejected      = status_counts.get("rejected", 0)
    stale         = status_counts.get("stale", 0)
    ready         = status_counts.get("ready_to_apply", 0)

    # ── Follow-ups ────────────────────────────────────────────────────────────
    overdue_apps = [
        a for a in apps
        if a.get("follow_up_due", "") <= TODAY
        and a.get("status") in ("applied", "outreach_sent", "interviewing")
    ]
    due_tomorrow = [
        a for a in apps
        if a.get("follow_up_due", "") == TOMORROW
        and a.get("status") in ("applied", "outreach_sent", "interviewing")
    ]

    # ── Today's new jobs ──────────────────────────────────────────────────────
    todays_jobs = [
        j for j in scored_jobs
        if j.get("scraped_at", "")[:10] == TODAY
        and j.get("score", 0) >= 6
        and j.get("visa_status") != "no-sponsorship"
        and not j.get("discard")
    ]
    todays_jobs.sort(key=lambda x: x.get("score", 0), reverse=True)

    # ── Applied today ─────────────────────────────────────────────────────────
    applied_today = [a for a in apps if a.get("applied_date", "") == TODAY]

    # ── Streak (consecutive days with activity) ───────────────────────────────
    active_dates = sorted(set(
        a.get("applied_date", "") for a in apps if a.get("applied_date")
    ), reverse=True)
    streak = 0
    check = date.today()
    for d in active_dates:
        if d == check.isoformat():
            streak += 1
            check -= timedelta(days=1)
        else:
            break

    # ── Build Slack blocks ────────────────────────────────────────────────────
    now_str = datetime.now().strftime("%A, %B %-d")  # e.g. "Sunday, May 25"

    header = f"*📊 Daily Job Hunt Report — {now_str}*"

    # Pipeline section
    pipeline_lines = [
        f"*Pipeline Status*",
        f"• Total applications: *{total}*",
        f"• Applied / Outreach sent: *{applied}*",
        f"• Interviewing: *{interviewing}*" + (" 🎯" if interviewing else ""),
        f"• Offers: *{offers}*" + (" 🏆" if offers else ""),
        f"• Ready to apply: *{ready}*",
        f"• Rejected / Stale: {rejected + stale}",
    ]
    if streak > 1:
        pipeline_lines.append(f"• Apply streak: *{streak} days* 🔥")

    pipeline_text = "\n".join(pipeline_lines)

    # Follow-ups section
    followup_lines = [f"*Follow-ups*"]
    if overdue_apps:
        followup_lines.append(f"🔴 *{len(overdue_apps)} overdue:*")
        for a in overdue_apps[:5]:
            followup_lines.append(f"  • {a['company']} — {a.get('role','')[:30]} (due {a.get('follow_up_due','')})")
        if len(overdue_apps) > 5:
            followup_lines.append(f"  _...and {len(overdue_apps)-5} more_")
    else:
        followup_lines.append("✅ No overdue follow-ups")

    if due_tomorrow:
        followup_lines.append(f"🟡 *Due tomorrow:*")
        for a in due_tomorrow[:3]:
            followup_lines.append(f"  • {a['company']} — {a.get('role','')[:30]}")

    followup_text = "\n".join(followup_lines)

    # Today's activity
    activity_lines = [f"*Today's Activity*"]
    if applied_today:
        activity_lines.append(f"📝 Applied today: *{len(applied_today)}*")
        for a in applied_today[:3]:
            activity_lines.append(f"  • {a['company']} — {a.get('role','')[:30]} (score: {a.get('score',0)})")
    else:
        activity_lines.append("No applications submitted today")

    if todays_jobs:
        activity_lines.append(f"\n🔍 New matches found today: *{len(todays_jobs)}*")
        for j in todays_jobs[:3]:
            company = j.get("company", "Unknown")
            title   = j.get("title", "")[:30]
            score   = j.get("score", 0)
            visa    = j.get("visa_status", "unknown")
            visa_icon = "✅" if visa == "confirmed" else "❓"
            activity_lines.append(f"  • {company} — {title} | Score: {score} | Visa: {visa_icon}")
        if len(todays_jobs) > 3:
            activity_lines.append(f"  _...and {len(todays_jobs)-3} more_")
    else:
        activity_lines.append("No new matches found today (run daily scan?)")

    activity_text = "\n".join(activity_lines)

    # Motivation nudge
    if offers:
        nudge = "🏆 You have an offer! Review and decide."
    elif interviewing:
        nudge = f"🎯 {interviewing} active interview(s) — prep and follow up!"
    elif overdue_apps:
        nudge = f"⚡ {len(overdue_apps)} follow-up(s) overdue — send them now."
    elif ready:
        nudge = f"🚀 {ready} job(s) ready to apply — hit submit tonight!"
    elif todays_jobs:
        nudge = f"💡 {len(todays_jobs)} new matches waiting — run outreach pipeline."
    else:
        nudge = "📅 Keep the momentum. Run a scan tomorrow morning at 8am."

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"📊 Daily Report — {now_str}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": pipeline_text}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": followup_text}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": activity_text}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"_{nudge}_"}},
    ]

    return {
        "text": header,  # fallback for notifications
        "blocks": blocks,
    }


def main():
    parser = argparse.ArgumentParser(description="Send daily job hunt status to Slack")
    parser.add_argument("--dry-run", action="store_true", help="Print digest without sending")
    args = parser.parse_args()

    apps        = load_json(APPS_FILE, [])
    scored_jobs = load_json(SCORED_FILE, [])

    payload = build_digest(apps, scored_jobs)

    # Preview
    print("=" * 60)
    print("DAILY STATUS DIGEST")
    print("=" * 60)
    for block in payload["blocks"]:
        if block["type"] == "section":
            print(block["text"]["text"])
            print()
        elif block["type"] == "divider":
            print("─" * 40)
    print("=" * 60)

    if args.dry_run:
        print("\n[dry-run] Not sent to Slack")
        return

    if not WEBHOOK_URL:
        print("\n❌ SLACK_WEBHOOK_URL not set — export it in .env")
        sys.exit(1)

    ok = send_slack(payload)
    if ok:
        print(f"\n✅ Digest sent to Slack ({datetime.now().strftime('%H:%M')})")
    else:
        print("\n❌ Failed to send digest")
        sys.exit(1)


if __name__ == "__main__":
    main()
