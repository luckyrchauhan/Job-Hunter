#!/usr/bin/env python3
"""
Job Hunter — Telegram Command Bot
Runs as a systemd service, polls for commands, triggers scans.

Commands:
  /scan    — run full daily scan now
  /status  — show last scan time + top scored jobs
  /digest  — send today's job digest
  /help    — show available commands
"""

import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE_DIR   = Path(__file__).parent.parent
SCORED_FILE = BASE_DIR / "data" / "jobs-scored.json"
LOG_FILE    = BASE_DIR / "logs" / "daily-scan.log"

POLL_INTERVAL = 3  # seconds


def get_env():
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    return (
        os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        os.environ.get("TELEGRAM_CHAT_ID", ""),
    )


def telegram_request(token: str, method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"Telegram API error: {e}")
        return {}


def send(token: str, chat_id: str, text: str):
    telegram_request(token, "sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    })


def get_updates(token: str, offset: int) -> list:
    result = telegram_request(token, "getUpdates", {
        "offset": offset,
        "timeout": 2,
        "allowed_updates": ["message"],
    })
    return result.get("result", [])


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_help(token, chat_id):
    send(token, chat_id,
        "🤖 <b>Job Hunter Bot</b>\n\n"
        "/scan — run full scan now\n"
        "/status — last scan + top jobs\n"
        "/digest — today's job digest\n"
        "/help — this message"
    )


def cmd_scan(token, chat_id):
    send(token, chat_id, "⏳ Starting full scan... (takes 5-10 min, I'll ping you when done)")
    scan_script = BASE_DIR / "scripts" / "daily-scan.sh"
    try:
        proc = subprocess.Popen(
            ["/bin/bash", str(scan_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(BASE_DIR),
        )
        proc.wait(timeout=900)
        send(token, chat_id, "✅ Scan complete! Check your alerts above.")
    except subprocess.TimeoutExpired:
        proc.kill()
        send(token, chat_id, "⚠️ Scan timed out after 15 min.")
    except Exception as e:
        send(token, chat_id, f"❌ Scan failed: {e}")


def cmd_status(token, chat_id):
    lines = ["📊 <b>Job Hunter Status</b>\n"]

    # Last scan time from log
    if LOG_FILE.exists():
        log_lines = LOG_FILE.read_text().splitlines()
        last_scan = next((l for l in reversed(log_lines) if "Scan complete" in l or "Daily Scan —" in l), None)
        if last_scan:
            lines.append(f"🕐 Last scan: {last_scan.strip()}")
    else:
        lines.append("🕐 No scans run yet")

    # Top jobs from scored file
    if SCORED_FILE.exists():
        with open(SCORED_FILE) as f:
            jobs = json.load(f)
        good = [j for j in jobs if not j.get("discard") and j.get("score", 0) >= 7.0]
        good = sorted(good, key=lambda j: j.get("score", 0), reverse=True)[:5]
        if good:
            lines.append(f"\n🏆 Top {len(good)} jobs today:")
            for j in good:
                score = j.get("score", 0)
                title = j.get("title", "?")
                company = j.get("company", "?")
                url = j.get("apply_url", "")
                lines.append(f"  [{score}] <a href=\"{url}\">{title} @ {company}</a>")
        else:
            lines.append("\nNo strong matches yet — run /scan")
    else:
        lines.append("\nNo scored jobs yet — run /scan")

    send(token, chat_id, "\n".join(lines))


def cmd_digest(token, chat_id):
    python = BASE_DIR / "venv" / "bin" / "python"
    notifier = BASE_DIR / "scripts" / "notify_slack.py"
    try:
        subprocess.run([str(python), str(notifier), "--digest"],
                       cwd=str(BASE_DIR), timeout=30)
        # digest sends its own Telegram messages via notify_slack.py
    except Exception as e:
        send(token, chat_id, f"❌ Digest failed: {e}")


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    get_env()
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return

    print(f"[Bot] Starting — polling every {POLL_INTERVAL}s")
    send(token, chat_id, "🟢 Job Hunter bot online. Type /help for commands.")

    offset = 0
    while True:
        try:
            updates = get_updates(token, offset)
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                from_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "").strip().lower()

                # Only respond to authorized chat
                if from_id != chat_id:
                    continue

                print(f"[Bot] Command: {text}")

                if text.startswith("/scan"):
                    cmd_scan(token, chat_id)
                elif text.startswith("/status"):
                    cmd_status(token, chat_id)
                elif text.startswith("/digest"):
                    cmd_digest(token, chat_id)
                elif text.startswith("/help") or text.startswith("/start"):
                    cmd_help(token, chat_id)
                else:
                    send(token, chat_id, "Unknown command. Type /help")

        except KeyboardInterrupt:
            print("[Bot] Stopped")
            break
        except Exception as e:
            print(f"[Bot] Error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
