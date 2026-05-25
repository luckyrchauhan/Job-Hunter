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

PM_TAGS = {"product", "product manager", "pm", "product management", "saas", "b2b"}

def main():
    os.makedirs("data/jobs-raw", exist_ok=True)
    
    headers = {"User-Agent": "Job Hunter Bot (lucky.raajc@gmail.com)"}
    resp = requests.get("https://remoteok.com/api", headers=headers, timeout=30)
    
    if resp.status_code != 200:
        print(f"RemoteOK: HTTP {resp.status_code}"); return
    
    raw = resp.json()
    # First item is metadata
    jobs_raw = [j for j in raw if isinstance(j, dict) and j.get("position")]
    
    pm_jobs = []
    for j in jobs_raw:
        tags = [t.lower() for t in (j.get("tags") or [])]
        title = (j.get("position") or "").lower()
        
        if any(t in PM_TAGS for t in tags) or "product manager" in title or "product management" in title:
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
