"""
RemoteOK Job Scraper — JSON API (no auth needed)
Saves to: data/jobs-raw/remoteok-YYYY-MM-DD.json
"""
import os, json, requests
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"data/jobs-raw/remoteok-{DATE}.json"

PM_TITLE_TOKENS = ["product manager", "product management", "head of product", "director of product",
                   "vp of product", "vp product", "group product manager", "staff product manager",
                   "principal product manager", "associate product manager", "apm"]

def is_pm_title(title: str) -> bool:
    """Require 'product manager' variant in title — avoids Designer/SDR/Dev false positives."""
    t = title.lower()
    return any(tok in t for tok in PM_TITLE_TOKENS)

def main():
    os.makedirs("data/jobs-raw", exist_ok=True)

    headers = {"User-Agent": "Job Hunter Bot (your.email@example.com)"}
    resp = requests.get("https://remoteok.com/api", headers=headers, timeout=30)

    if resp.status_code != 200:
        print(f"RemoteOK: HTTP {resp.status_code}"); return

    raw = resp.json()
    # First item is metadata
    jobs_raw = [j for j in raw if isinstance(j, dict) and j.get("position")]

    pm_jobs = []
    for j in jobs_raw:
        title = (j.get("position") or "")
        tags = [t.lower() for t in (j.get("tags") or [])]

        # Title must match PM — tags alone are too broad (catches Designer/SDR/Dev)
        if is_pm_title(title):
            pm_jobs.append({
                "id": f"remoteok-{j.get('id','')}",
                "source": "remoteok",
                "title": j.get("position", ""),
                "company": j.get("company", ""),
                "location": "Remote",
                "remote": True,
                "salary_min": j.get("salary_min"),
                "salary_max": j.get("salary_max"),
                "posted_date": j.get("date", ""),
                "apply_url": j.get("apply_url") or j.get("url", ""),
                "description": (j.get("description") or "")[:2000],
                "tags": j.get("tags", []),
                "scraped_at": datetime.now().isoformat(),
            })
    
    with open(OUT_FILE, "w") as f:
        json.dump(pm_jobs, f, indent=2)
    print(f"RemoteOK: {len(pm_jobs)} PM jobs saved to {OUT_FILE}")

if __name__ == "__main__":
    main()
