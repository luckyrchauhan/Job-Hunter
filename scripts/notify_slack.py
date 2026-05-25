#!/usr/bin/env python3
"""
M4 — Slack Notifier
Reads: data/jobs-scored.json
Sends: Slack alerts for urgency_tier ≤ 4 (APPLY NOW / <15 HOURS)
Daily digest: tiers 5–6

Usage:
  python3 scripts/notify_slack.py          # immediate alerts only
  python3 scripts/notify_slack.py --digest # daily digest (all good+ matches)
  python3 scripts/notify_slack.py --test   # test message
"""

import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SCORED_FILE = BASE_DIR / "data" / "jobs-scored.json"
NOTIFIED_FILE = BASE_DIR / "data" / "notified-ids.json"

WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# ─── Helpers ──────────────────────────────────────────────────────────────────

def send_slack(payload: dict) -> bool:
    if not WEBHOOK_URL:
        print("❌ SLACK_WEBHOOK_URL not set in .env")
        return False
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(WEBHOOK_URL, data=data,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"❌ Slack error: {e}")
        return False


def load_notified() -> set:
    if NOTIFIED_FILE.exists():
        with open(NOTIFIED_FILE) as f:
            return set(json.load(f))
    return set()


def save_notified(ids: set):
    with open(NOTIFIED_FILE, "w") as f:
        json.dump(list(ids), f, indent=2)


def load_scored() -> list:
    if not SCORED_FILE.exists():
        print(f"❌ {SCORED_FILE} not found. Run score_jobs.py first.")
        return []
    with open(SCORED_FILE) as f:
        return json.load(f)

# ─── Formatters ───────────────────────────────────────────────────────────────

TIER_EMOJI = {1: "🔴", 2: "🔴", 3: "🟠", 4: "🟠", 5: "🟡", 6: "🟡", 7: "⚪", 8: "⛔"}
VISA_EMOJI = {"tier_1_heavy_sponsors": "✅", "tier_2_consistent_sponsors": "✅",
              "tier_3_startup_sponsors": "⚠️", "tier_4_verify_first": "🔍",
              "jd_confirmed": "✅", "unknown": "❓", "no_sponsorship": "❌"}


def format_job_alert(job: dict) -> dict:
    """Single job — immediate alert format."""
    tier = job.get("urgency_tier", 7)
    score = job.get("score", 0)
    company = job.get("company") or "Unknown Company"
    title = job.get("title", "?")
    url = job.get("apply_url", "")
    band = job.get("score_band", "?")
    visa_status = job.get("visa_status_raw") or job.get("visa_status", "unknown")
    visa_icon = VISA_EMOJI.get(visa_status, "❓")
    tier_icon = TIER_EMOJI.get(tier, "⚪")
    urgency_label = job.get("urgency_label", "?")
    days = job.get("days_since_posted", "?")
    breakdown = job.get("score_breakdown", {})
    ai_score = breakdown.get("ai_llm", 0)
    sc_score = breakdown.get("supply_chain", 0)

    tags = []
    if ai_score > 0:
        tags.append("🤖 AI/LLM")
    if sc_score > 0:
        tags.append("🏭 Supply Chain")
    if job.get("remote"):
        tags.append("🌎 Remote")
    if job.get("low_confidence"):
        tags.append("⚠️ Low data")

    tag_str = "  ".join(tags) if tags else "—"

    return {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{tier_icon} {urgency_label} — Apply Now"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*\n{company}"
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Apply →"},
                    "url": url,
                    "style": "primary"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Score:* {score}/10 ({band})"},
                    {"type": "mrkdwn", "text": f"*Visa:* {visa_icon} {visa_status.replace('_', ' ')}"},
                    {"type": "mrkdwn", "text": f"*Posted:* {days} days ago"},
                    {"type": "mrkdwn", "text": f"*Tags:* {tag_str}"},
                ]
            },
            {"type": "divider"}
        ]
    }


def format_digest(jobs: list) -> dict:
    """Daily digest — all good/strong matches."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"*📋 Job Hunter Daily Digest — {now}*\n"]
    lines.append(f"_{len(jobs)} matches found_\n")

    for j in jobs:
        tier = j.get("urgency_tier", 7)
        score = j.get("score", 0)
        company = j.get("company") or "Unknown"
        title = j.get("title", "?")
        url = j.get("apply_url", "")
        visa_status = j.get("visa_status_raw") or j.get("visa_status", "unknown")
        visa_icon = VISA_EMOJI.get(visa_status, "❓")
        tier_icon = TIER_EMOJI.get(tier, "⚪")

        lines.append(f"{tier_icon} *[{score}]* <{url}|{title}> — {company} {visa_icon}")

    return {"text": "\n".join(lines)}

# ─── Main ─────────────────────────────────────────────────────────────────────

def send_test():
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🎯 Job Hunter — Test Message"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "M4 Slack notifier working ✅\nYou'll get alerts here for matching PM jobs."
                }
            }
        ]
    }
    ok = send_slack(payload)
    print("✅ Test message sent to Slack" if ok else "❌ Failed")


def send_alerts():
    jobs = load_scored()
    notified = load_notified()
    new_notified = set()
    sent = 0

    alert_jobs = [j for j in jobs
                  if not j.get("discard")
                  and j.get("urgency_tier", 9) <= 4
                  and j.get("score", 0) >= 4.0
                  and j.get("id") not in notified]

    if not alert_jobs:
        print("No new urgent jobs to alert.")
        return

    for job in alert_jobs:
        payload = format_job_alert(job)
        ok = send_slack(payload)
        if ok:
            new_notified.add(job.get("id"))
            sent += 1
            print(f"  ✅ Alert sent: {job.get('title')} @ {job.get('company')}")
        else:
            print(f"  ❌ Failed: {job.get('title')}")

    save_notified(notified | new_notified)
    print(f"\n📤 Sent {sent} alerts.")


def send_digest():
    jobs = load_scored()
    good_jobs = [j for j in jobs
                 if not j.get("discard")
                 and j.get("score", 0) >= 6.0]

    if not good_jobs:
        print("No good matches for digest.")
        # Send "nothing today" message
        send_slack({"text": "📋 *Job Hunter Digest* — No strong matches today. Keep searching! 💪"})
        return

    payload = format_digest(good_jobs)
    ok = send_slack(payload)
    print(f"✅ Digest sent ({len(good_jobs)} jobs)" if ok else "❌ Digest failed")


if __name__ == "__main__":
    # Load .env manually (no python-dotenv needed)
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

    mode = sys.argv[1] if len(sys.argv) > 1 else "--alerts"

    if mode == "--test":
        send_test()
    elif mode == "--digest":
        send_digest()
    else:
        send_alerts()
