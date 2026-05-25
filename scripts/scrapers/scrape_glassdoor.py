"""
Glassdoor Job Scraper
Primary: Apify actor crawlector/glassdoor-jobs-scraper
Fallback: Apify actor GS7bk1h4jsMxTpyxX (alternative)
Saves to: data/jobs-raw/glassdoor-YYYY-MM-DD.json

Usage:
  python scripts/scrapers/scrape_glassdoor.py
  python scripts/scrapers/scrape_glassdoor.py --max 100

Requires: APIFY_API_TOKEN in .env
"""
import os, json, time, argparse
from datetime import datetime
import requests
from dotenv import load_dotenv
load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"data/jobs-raw/glassdoor-{DATE}.json"
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN", "")

SEARCHES = [
    {"keyword": "product manager", "location": "United States"},
    {"keyword": "senior product manager", "location": "United States"},
    {"keyword": "AI product manager", "location": "United States"},
]

PM_TITLES = [
    "product manager", "senior product manager", "sr. product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "head of product", "director of product",
]

def is_pm_title(title: str) -> bool:
    t = title.lower()
    return any(pm in t for pm in PM_TITLES)


def run_actor(actor_id: str, payload: dict, timeout: int = 180) -> list:
    base_url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
    try:
        resp = requests.post(
            base_url,
            params={"token": APIFY_TOKEN, "timeout": timeout, "memory": 1024},
            json=payload,
            timeout=timeout + 30,
        )
        if resp.status_code not in (200, 201):
            print(f"    HTTP {resp.status_code}: {resp.text[:200]}")
            return []
        data = resp.json()
        return data if isinstance(data, list) else data.get("items", [])
    except requests.Timeout:
        print(f"    Actor timed out")
        return []
    except Exception as e:
        print(f"    Actor error: {e}")
        return []


def scrape_glassdoor(max_results: int = 50) -> list:
    if not APIFY_TOKEN:
        print("  ⚠ APIFY_API_TOKEN not set — skipping Glassdoor")
        return []

    all_jobs = []
    seen = set()

    for search in SEARCHES:
        print(f"  Glassdoor Apify: '{search['keyword']}'")

        # Primary actor
        payload = {
            "keyword": search["keyword"],
            "location": search["location"],
            "maxItems": max_results,
            "remoteFilter": True,
            "datePosted": "last7days",
        }
        items = run_actor("crawlector~glassdoor-jobs-scraper", payload, timeout=180)

        # Fallback actor
        if not items:
            payload2 = {
                "searchTerms": [search["keyword"]],
                "location": search["location"],
                "maxItems": max_results,
            }
            items = run_actor("GS7bk1h4jsMxTpyxX", payload2, timeout=180)

        print(f"    → {len(items)} raw items")

        for item in items:
            title = item.get("jobTitle", item.get("title", item.get("position", "")))
            if not title or not is_pm_title(title):
                continue

            job_id = str(item.get("id", item.get("jobId", item.get("url", "")[:80])))
            if job_id in seen:
                continue
            seen.add(job_id)

            company = item.get("employerName", item.get("company", item.get("companyName", "")))
            if isinstance(company, dict):
                company = company.get("name", "")

            salary_text = item.get("salary", item.get("salaryText", item.get("payPeriod", "")))
            location = item.get("location", item.get("jobLocation", search["location"]))

            all_jobs.append({
                "id": f"glassdoor-{job_id}",
                "source": "glassdoor",
                "title": title.strip(),
                "company": company.strip() if isinstance(company, str) else "",
                "location": location if isinstance(location, str) else str(location),
                "remote": "remote" in str(location).lower() or item.get("isRemote", False),
                "salary_text": salary_text if isinstance(salary_text, str) else "",
                "salary_min": None, "salary_max": None,
                "posted_date": str(item.get("datePosted", item.get("postedAt", DATE)))[:10],
                "apply_url": item.get("jobUrl", item.get("applyUrl", item.get("url", ""))),
                "description": (item.get("description", item.get("jobDescription", "")) or "")[:2000],
                "source_query": f"{search['keyword']} | {search['location']}",
                "scraped_at": datetime.now().isoformat(),
            })

        time.sleep(3)

    return all_jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=50)
    args = parser.parse_args()

    os.makedirs("data/jobs-raw", exist_ok=True)

    if not APIFY_TOKEN:
        print("Glassdoor: APIFY_API_TOKEN not set — no jobs scraped")
        with open(OUT_FILE, "w") as f:
            json.dump([], f)
        return

    jobs = scrape_glassdoor(max_results=args.max)
    seen = set()
    unique = [j for j in jobs if j["id"] not in seen and not seen.add(j["id"])]

    with open(OUT_FILE, "w") as f:
        json.dump(unique, f, indent=2)
    print(f"\nGlassdoor: {len(unique)} PM jobs saved to {OUT_FILE}")


if __name__ == "__main__":
    main()
