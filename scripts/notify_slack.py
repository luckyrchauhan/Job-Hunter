#!/usr/bin/env python3
"""
M4 — Telegram Notifier
Reads: data/jobs-scored.json
Sends: Telegram alerts for urgency_tier <= 4 (APPLY NOW / <15 HOURS)
Daily digest: tiers 5-6

Usage:
  python3 scripts/notify_slack.py          # immediate alerts only
  python3 scripts/notify_slack.py --digest # daily digest (all good+ matches)
  python3 scripts/notify_slack.py --test   # test message

.env vars needed:
  TELEGRAM_BOT_TOKEN=123456:ABC-xyz
  TELEGRAM_CHAT_ID=987654321
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SCORED_FILE = BASE_DIR / "data" / "jobs-scored.json"
NOTIFIED_FILE = BASE_DIR / "data" / "notified-ids.json"

# ─── Telegram sender ──────────────────────────────────────────────────────────

def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("❌ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False


# ─── Helpers ──────────────────────────────────────────────────────────────────

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
VISA_EMOJI = {
    "tier_1_heavy_sponsors": "✅", "tier_2_consistent_sponsors": "✅",
    "tier_3_startup_sponsors": "⚠️", "tier_4_verify_first": "🔍",
    "jd_confirmed": "✅", "unknown": "❓", "no_sponsorship": "❌"
}


def format_job_alert(job: dict) -> str:
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

    tags = []
    if breakdown.get("ai_llm", 0) > 0:
        tags.append("🤖 AI/LLM")
    if breakdown.get("supply_chain", 0) > 0:
        tags.append("🏭 Supply Chain")
    if job.get("remote"):
        tags.append("🌎 Remote")
    tag_str = "  ".join(tags) if tags else "—"

    return (
        f"{tier_icon} <b>{urgency_label}</b>\n"
        f"<b>{title}</b>\n"
        f"🏢 {company}\n"
        f"⭐ Score: {score}/10 ({band})\n"
        f"🛂 Visa: {visa_icon} {visa_status.replace('_', ' ')}\n"
        f"📅 Posted: {days} days ago\n"
        f"🏷 {tag_str}\n"
        f"🔗 <a href=\"{url}\">Apply →</a>"
    )


def format_digest(jobs: list) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"📋 <b>Job Hunter Daily Digest — {now}</b>", f"<i>{len(jobs)} matches found</i>", ""]

    for j in jobs:
        tier = j.get("urgency_tier", 7)
        score = j.get("score", 0)
        company = j.get("company") or "Unknown"
        title = j.get("title", "?")
        url = j.get("apply_url", "")
        visa_status = j.get("visa_status_raw") or j.get("visa_status", "unknown")
        visa_icon = VISA_EMOJI.get(visa_status, "❓")
        tier_icon = TIER_EMOJI.get(tier, "⚪")
        lines.append(f"{tier_icon} [{score}] <a href=\"{url}\">{title}</a> — {company} {visa_icon}")

    return "\n".join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

def send_test():
    text = (
        "🎯 <b>Job Hunter — Test Message</b>\n"
        "Telegram notifier working ✅\n"
        "You'll get alerts here for matching PM jobs."
    )
    ok = send_telegram(text)
    print("✅ Test message sent to Telegram" if ok else "❌ Failed")


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
        text = format_job_alert(job)
        ok = send_telegram(text)
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
        send_telegram("📋 <b>Job Hunter Digest</b> — No strong matches today. Keep searching! 💪")
        return

    text = format_digest(good_jobs)
    ok = send_telegram(text)
    print(f"✅ Digest sent ({len(good_jobs)} jobs)" if ok else "❌ Digest failed")


if __name__ == "__main__":
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    mode = sys.argv[1] if len(sys.argv) > 1 else "--alerts"

    if mode == "--test":
        send_test()
    elif mode == "--digest":
        send_digest()
    else:
        send_alerts()
