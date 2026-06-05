#!/usr/bin/env python3
"""
Sends a Telegram summary after every daily scan.
Shows: total jobs, score breakdown, top 5 matches.
"""

import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

BASE_DIR    = Path(__file__).parent.parent
SCORED_FILE = BASE_DIR / "data" / "jobs-scored.json"


def send_telegram(text: str) -> bool:
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("  ⚠ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return False
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  ✗ Telegram error: {e}")
        return False


def main():
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    if not SCORED_FILE.exists():
        send_telegram("⚠️ <b>Scan Summary</b>\nNo scored jobs file found.")
        return

    with open(SCORED_FILE) as f:
        jobs = json.load(f)

    total    = len(jobs)
    strong   = [j for j in jobs if not j.get("discard") and j.get("score", 0) >= 8.0]
    good     = [j for j in jobs if not j.get("discard") and 6.0 <= j.get("score", 0) < 8.0]
    weak     = [j for j in jobs if not j.get("discard") and 4.0 <= j.get("score", 0) < 6.0]
    discard  = [j for j in jobs if j.get("discard")]
    top5     = sorted([j for j in jobs if not j.get("discard")],
                      key=lambda j: j.get("score", 0), reverse=True)[:5]

    now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"📊 <b>Scan Complete — {now}</b>",
        f"",
        f"📦 Total scored: <b>{total}</b>",
        f"🟢 Strong (≥8): <b>{len(strong)}</b>",
        f"🔵 Good  (≥6): <b>{len(good)}</b>",
        f"🟡 Weak  (≥4): <b>{len(weak)}</b>",
        f"❌ Discarded:  <b>{len(discard)}</b>",
    ]

    if top5:
        lines.append("")
        lines.append("🏆 <b>Top Matches:</b>")
        for j in top5:
            score   = j.get("score", 0)
            title   = j.get("title", "?")
            company = j.get("company", "?")
            url     = j.get("apply_url", "")
            visa    = "✅" if j.get("visa_status", "") in [
                "tier_1_heavy_sponsors", "tier_2_consistent_sponsors", "jd_confirmed"
            ] else "❓"
            lines.append(f"  [{score}] {visa} <a href=\"{url}\">{title} @ {company}</a>")

    send_telegram("\n".join(lines))


if __name__ == "__main__":
    main()
