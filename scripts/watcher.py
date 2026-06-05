#!/usr/bin/env python3
"""
Job Hunter — Instant Alert Watcher
Polls lightweight job sources every 15 minutes (8am–8pm EDT).
Sends immediate Telegram alert for: score >= 8 AND posted < 2hrs AND applicants < 50.

Runs independently from daily-scan.sh — does NOT do full scrape.
Uses free public APIs only (RemoteOK, Himalayas, YC).

Usage:
  python scripts/watcher.py          # single poll cycle (run via cron */15)
  python scripts/watcher.py --dry-run  # score + print matches, no Telegram
  python scripts/watcher.py --test     # send test Telegram alert + exit

.env vars needed:
  TELEGRAM_BOT_TOKEN=123456:ABC-xyz
  TELEGRAM_CHAT_ID=987654321

Cron entry (every 15min, 8am–8pm):
  */15 8-20 * * * /path/to/venv/bin/python /path/to/scripts/watcher.py >> /path/to/logs/watcher.log 2>&1
"""

import json
import os
import sys
import hashlib
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR    = Path(__file__).parent.parent
SEEN_FILE   = BASE_DIR / "data" / "watcher-seen.json"
SCORED_FILE = BASE_DIR / "data" / "jobs-scored.json"
PARAMS_FILE = BASE_DIR / "config" / "search-params.json"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

# ── Config ────────────────────────────────────────────────────────────────────

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
    trimmed = list(ids)[-500:]  # cap at 500 to avoid unbounded growth
    SEEN_FILE.write_text(json.dumps({"ids": trimmed}, indent=2))

# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("  ⚠ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — alert skipped")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = resp.status == 200
            print("  ✓ Telegram alert sent" if ok else "  ✗ Telegram returned non-200")
            return ok
    except Exception as e:
        print(f"  ✗ Telegram error: {e}")
        return False


def build_instant_alert(job: dict) -> str:
    urgency_emoji = {
        "apply-now-critical": "🔴🔴",
        "apply-now-hot":      "🔴",
        "apply-now-today":    "🟠",
    }.get(job.get("urgency", ""), "⚡")

    score   = job.get("score", "?")
    title   = job.get("title", "Unknown Role")
    company = job.get("company", "Unknown")
    posted  = job.get("posted_text", "recently")
    salary  = job.get("salary_text", "Not listed")
    visa    = job.get("visa", "unclear")
    url     = job.get("apply_url", job.get("url", ""))
    source  = job.get("source", "")

    visa_icon = {"confirmed": "✅", "likely": "🟡", "unclear": "❓"}.get(visa, "❓")

    return (
        f"{urgency_emoji} <b>INSTANT ALERT — Score: {score}/10</b>\n"
        f"<b>Role:</b> {title}\n"
        f"<b>Company:</b> {company}\n"
        f"<b>Posted:</b> {posted}\n"
        f"<b>Salary:</b> {salary}\n"
        f"<b>Visa:</b> {visa_icon} {visa.title()}\n"
        f"<b>Source:</b> {source}\n"
        f"🔗 <a href=\"{url}\">Apply →</a>\n"
        f"<i>⚡ Watcher fired at {datetime.now().strftime('%H:%M')} UTC</i>"
    )

# ── Heuristic scorer (no API cost) ───────────────────────────────────────────

def quick_score(job: dict) -> int:
    """
    Fast heuristic score 1–10. No Claude API — avoids cost on every 15-min poll.
    Daily scan will do full AI scoring on confirmed matches.
    """
    title_text = job.get("title", "").lower()
    desc_text  = job.get("description", "").lower()
    full_text  = title_text + " " + desc_text

    # MUST have PM title — no PM title = max score 4 (never triggers instant alert)
    pm_title_match = any(t in title_text for t in [
        "product manager", "senior pm", "principal pm",
        "director of product", "head of product",
        "platform pm", "ai pm", "apm", "associate pm",
        "vp of product", "vp product", "group pm"
    ])
    if not pm_title_match:
        return 4  # hard cap — won't trigger ≥8 alert

    score = 5  # baseline (only reached if PM title matched)

    # PM seniority boost
    if any(t in title_text for t in ["senior", "principal", "director", "vp", "group", "lead"]):
        score += 1

    # AI/LLM signal (+1.5)
    if any(k in full_text for k in ["llm", "generative ai", "machine learning", "ai product"]):
        score += 1.5
    elif "ai" in title_text:
        score += 1

    # Enterprise/platform signal (+1)
    if any(k in full_text for k in ["enterprise", "platform", "saas", "b2b"]):
        score += 1

    # Negative signals
    if any(k in title_text for k in ["intern", "junior", "entry level", "associate"]):
        score -= 2
    if any(k in title_text for k in ["marketing", "sales", "hardware", "embedded", "engineering manager"]):
        score -= 3

    return min(10, max(1, round(score)))


def is_recent(job: dict, max_hours: int) -> bool:
    """True if job posted within max_hours. Unknown post time → assume recent."""
    posted = job.get("posted_at", "")
    if not posted:
        return True
    try:
        if posted.endswith("Z"):
            posted = posted[:-1] + "+00:00"
        dt = datetime.fromisoformat(posted)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt) <= timedelta(hours=max_hours)
    except (ValueError, TypeError):
        return True  # parse failure → assume recent


def age_text(posted_at: str) -> str:
    """Human-readable age string e.g. '47 minutes ago'."""
    if not posted_at:
        return "recently"
    try:
        p = posted_at.rstrip("Z") + ("+00:00" if posted_at.endswith("Z") else "")
        dt = datetime.fromisoformat(p)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        mins = int((datetime.now(timezone.utc) - dt).total_seconds() / 60)
        if mins < 60:
            return f"{mins} minutes ago"
        return f"{mins // 60} hours ago"
    except Exception:
        return "recently"


def assign_urgency(posted_at: str) -> str:
    if not posted_at:
        return "apply-now-hot"
    try:
        p = posted_at.rstrip("Z") + ("+00:00" if posted_at.endswith("Z") else "")
        dt = datetime.fromisoformat(p)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        mins = int((datetime.now(timezone.utc) - dt).total_seconds() / 60)
        if mins < 60:
            return "apply-now-critical"
        return "apply-now-hot"
    except Exception:
        return "apply-now-hot"


def make_job_id(job: dict) -> str:
    url = job.get("apply_url", job.get("url", ""))
    if url:
        return hashlib.md5(url.encode()).hexdigest()[:12]
    raw = f"{job.get('company','')}-{job.get('title','')}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]

# ── Delta scrapers (lightweight — no Apify) ───────────────────────────────────

def fetch_remoteok() -> list:
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
            if not any(t in title.lower() for t in ["product", "pm"]):
                continue
            salary_min = item.get("salary_min", "")
            salary_max = item.get("salary_max", "")
            salary_text = f"${salary_min}–${salary_max}" if salary_min else ""
            jobs.append({
                "title":       title,
                "company":     item.get("company", ""),
                "apply_url":   item.get("url", f"https://remoteok.com/l/{item.get('id','')}"),
                "posted_at":   item.get("date", ""),
                "salary_text": salary_text,
                "source":      "RemoteOK",
                "description": " ".join(item.get("tags", [])),
            })
        return jobs
    except Exception as e:
        print(f"  ⚠ RemoteOK: {e}")
        return []


def fetch_himalayas() -> list:
    try:
        url = "https://himalayas.app/jobs/api?q=product+manager&limit=20&remoteOnly=true"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        jobs = []
        for item in data.get("jobs", []):
            jobs.append({
                "title":       item.get("title", ""),
                "company":     item.get("company", {}).get("name", ""),
                "apply_url":   item.get("applicationLink", item.get("url", "")),
                "posted_at":   item.get("publishedAt", ""),
                "salary_text": item.get("salaryRange", ""),
                "source":      "Himalayas",
                "description": item.get("description", "")[:500],
            })
        return jobs
    except Exception as e:
        print(f"  ⚠ Himalayas: {e}")
        return []


def fetch_yc() -> list:
    try:
        url = "https://api.workatastartup.com/jobs?query=product+manager&remote=true&limit=20"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        jobs = []
        for item in data.get("jobs", []):
            jobs.append({
                "title":       item.get("title", ""),
                "company":     item.get("company", {}).get("name", ""),
                "apply_url":   f"https://www.workatastartup.com/jobs/{item.get('id','')}",
                "posted_at":   item.get("created_at", ""),
                "salary_text": "",
                "source":      "YC",
                "description": item.get("description", "")[:500],
            })
        return jobs
    except Exception as e:
        print(f"  ⚠ YC: {e}")
        return []

# ── Append to jobs-scored.json ────────────────────────────────────────────────

def append_to_scored(job: dict):
    scored = []
    if SCORED_FILE.exists():
        content = SCORED_FILE.read_text().strip()
        if content:
            scored = json.loads(content)
    existing_ids = {j.get("id") for j in scored}
    if job["id"] not in existing_ids:
        scored.append(job)
        SCORED_FILE.write_text(json.dumps(scored, indent=2))


def sync_job_to_sheets(job: dict):
    """Best-effort Google Sheets upsert — skip silently if not configured."""
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

# ── Main poll ─────────────────────────────────────────────────────────────────

def poll(params: dict, dry_run: bool = False) -> int:
    score_threshold = int(params.get("instant_alert_score_threshold", 8))
    max_age_hours   = int(params.get("instant_alert_max_age_hours", 2))
    max_applicants  = int(params.get("instant_alert_max_applicants", 50))

    seen = load_seen()
    alerts_fired = 0

    print(f"\n[Watcher] {datetime.now().strftime('%Y-%m-%d %H:%M')} — polling...")

    all_jobs = fetch_remoteok() + fetch_himalayas() + fetch_yc()
    print(f"  Fetched {len(all_jobs)} raw jobs")

    new_jobs = []
    for job in all_jobs:
        jid = make_job_id(job)
        job["id"] = jid
        if jid not in seen:
            new_jobs.append(job)

    print(f"  {len(new_jobs)} unseen jobs to evaluate")

    for job in new_jobs:
        seen.add(job["id"])

        applicants = job.get("applicant_count", 0) or 0
        if applicants >= max_applicants:
            continue

        if not is_recent(job, max_age_hours):
            continue

        score = quick_score(job)
        job["score"] = score

        label = f"  {'🔴' if score >= score_threshold else '·'} {job.get('company','?'):20} — {job.get('title','')[:35]:35} score {score}/10"
        print(label)

        if score >= score_threshold:
            job["urgency"]     = assign_urgency(job.get("posted_at", ""))
            job["posted_text"] = age_text(job.get("posted_at", ""))
            job["visa"]        = "unclear"  # watcher doesn't do visa lookup — daily scan handles it

            if not dry_run:
                send_telegram(build_instant_alert(job))
                append_to_scored(job)
                sync_job_to_sheets(job)

            alerts_fired += 1

    save_seen(seen)
    print(f"\n[Watcher] Done — {alerts_fired} instant alert(s) fired")
    return alerts_fired


def test_alert():
    text = (
        "⚡ <b>Job Hunter Watcher — Test Alert</b>\n"
        "Watcher is configured correctly.\n"
        "Instant Telegram alerts will fire here for: score ≥ 8 + posted &lt; 2hrs + &lt; 50 applicants."
    )
    ok = send_telegram(text)
    print("✅ Test alert sent" if ok else "✗ Test failed — check TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID")


def main():
    # Load .env
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

    parser = argparse.ArgumentParser(description="Job Hunter instant alert watcher")
    parser.add_argument("--dry-run", action="store_true", help="Score + print, no Telegram")
    parser.add_argument("--test",    action="store_true", help="Send test Telegram alert")
    args = parser.parse_args()

    if args.test:
        test_alert()
        return

    params = load_params()

    # Active hours gate
    start_h = int(params.get("watcher_active_hours_start", 8))
    end_h   = int(params.get("watcher_active_hours_end", 20))
    now_h   = datetime.now().hour
    if not (start_h <= now_h < end_h) and not args.dry_run:
        print(f"[Watcher] Outside active hours ({start_h}–{end_h}) — exiting")
        return

    poll(params, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
