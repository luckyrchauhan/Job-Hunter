"""
Himalayas.app Job Scraper — clean JSON API, shows visa sponsorship
Saves to: data/jobs-raw/himalayas-YYYY-MM-DD.json
"""
import os, json, requests
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"data/jobs-raw/himalayas-{DATE}.json"

PM_TITLES = [
    "product manager", "senior product manager", "sr product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "group product manager", "director of product"
]

HEADERS = {"User-Agent": "JobHunter/1.0 (lucky.raajc@gmail.com)"}

def is_pm(title):
    return any(p in title.lower() for p in PM_TITLES)

def main():
    os.makedirs("data/jobs-raw", exist_ok=True)
    pm_jobs = []
    seen = set()

    # Himalayas paginates — fetch multiple pages
    # API: https://himalayas.app/jobs/api?q=product+manager&page=N&limit=50
    # Note: 'title' param is ignored; 'q' works as keyword search
    for page in range(1, 6):
        try:
            resp = requests.get(
                "https://himalayas.app/jobs/api",
                params={"q": "product manager", "page": page, "limit": 50,
                        "remoteOnly": "true"},
                headers=HEADERS, timeout=20
            )
            if resp.status_code != 200:
                print(f"  Page {page}: HTTP {resp.status_code}")
                break
            
            data = resp.json()
            jobs = data.get("jobs", [])
            if not jobs:
                break
            
            for j in jobs:
                title = j.get("title", "")
                job_id = str(j.get("id", j.get("slug", "")))
                
                if job_id in seen or not is_pm(title):
                    continue
                seen.add(job_id)
                
                pm_jobs.append({
                    "id": f"himalayas-{job_id}",
                    "source": "himalayas",
                    "title": title,
                    "company": j.get("companyName", j.get("company", {}).get("name", "") if isinstance(j.get("company"), dict) else ""),
                    "location": j.get("locationRestrictions", ["Remote"])[0] if j.get("locationRestrictions") else "Remote",
                    "remote": True,
                    "salary_min": j.get("salaryMin"),
                    "salary_max": j.get("salaryMax"),
                    "visa_sponsored": j.get("visaSponsorship", False),
                    "posted_date": j.get("publishedAt", DATE),
                    "apply_url": j.get("applicationLink") or f"https://himalayas.app/jobs/{job_id}",
                    "description": (j.get("description") or "")[:2000],
                    "tags": j.get("tags", []),
                    "scraped_at": datetime.now().isoformat(),
                })
            
            print(f"  Page {page}: {len(jobs)} total, {len(pm_jobs)} PM so far")
            
            if len(jobs) < 50:
                break
                
        except Exception as e:
            print(f"  Page {page} error: {e}")
            break

    with open(OUT_FILE, "w") as f:
        json.dump(pm_jobs, f, indent=2)
    print(f"Himalayas: {len(pm_jobs)} PM jobs saved to {OUT_FILE}")

if __name__ == "__main__":
    main()
