"""
LinkedIn Job Scraper
Primary: Apify actor JkfTWxtpgfvcRQn3p (Rapid LinkedIn Jobs Scraper)
Fallback: Apify actor hKByXkMQaC5Qt9UMN (LinkedIn Jobs Scraper)
Saves to: data/jobs-raw/linkedin-YYYY-MM-DD.json

Usage:
  python scripts/scrapers/scrape_linkedin.py
  python scripts/scrapers/scrape_linkedin.py --max 100

Requires: APIFY_API_TOKEN in .env
"""
import os, json, time, argparse
from datetime import datetime
import requests
from dotenv import load_dotenv
load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"data/jobs-raw/linkedin-{DATE}.json"
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN", "")

SEARCHES = [
    {"keywords": "product manager", "location": "United States"},
    {"keywords": "senior product manager", "location": "United States"},
    {"keywords": "AI product manager", "location": "United States"},
    {"keywords": "platform product manager", "location": "United States"},
]

PM_TITLES = [
    "product manager", "senior product manager", "sr. product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "head of product", "director of product", "vp of product",
    "group product manager",
]

def is_pm_title(title: str) -> bool:
    t = title.lower()
    return any(pm in t for pm in PM_TITLES)


def run_actor(actor_id: str, payload: dict, timeout: int = 180) -> list:
    """Run Apify actor sync and return items list."""
    base_url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
    try:
        resp = requests.post(
            base_url,
            params={"token": APIFY_TOKEN, "timeout": timeout, "memory": 512},
            json=payload,
            timeout=timeout + 30,
        )
        if resp.status_code not in (200, 201):
            print(f"    Actor {actor_id} HTTP {resp.status_code}: {resp.text[:200]}")
            return []
        data = resp.json()
        return data if isinstance(data, list) else data.get("items", [])
    except requests.Timeout:
        print(f"    Actor {actor_id} timed out")
        return []
    except Exception as e:
        print(f"    Actor {actor_id} error: {e}")
        return []


def scrape_linkedin(max_results: int = 50) -> list:
    if not APIFY_TOKEN:
        print("  ⚠ APIFY_API_TOKEN not set — skipping LinkedIn")
        return []

    all_jobs = []
    seen = set()

    # Actor 1: JkfTWxtpgfvcRQn3p — Rapid LinkedIn Jobs Scraper
    for search in SEARCHES:
        print(f"  LinkedIn Apify: '{search['keywords']}' @ '{search['location']}'")

        # Actor 1 payload format
        payload = {
            "keywords": search["keywords"],
            "location": search["location"],
            "dateSincePosted": "past week",
            "jobType": "full time",
            "remoteFilter": "remote",
            "limit": max_results,
        }

        items = run_actor("JkfTWxtpgfvcRQn3p", payload, timeout=180)

        # Fallback actor if first returns empty
        if not items:
            print(f"    Primary actor empty — trying fallback actor")
            payload2 = {
                "searchTerms": [search["keywords"]],
                "location": [search["location"]],
                "maxItems": max_results,
                "onlyRemote": True,
                "postedDate": "r604800",  # past week
            }
            items = run_actor("hKByXkMQaC5Qt9UMN", payload2, timeout=180)

        print(f"    → {len(items)} raw items")

        for item in items:
            title = item.get("title", item.get("positionName", item.get("jobTitle", "")))
            if not title or not is_pm_title(title):
                continue

            job_id = item.get("id", item.get("jobId", item.get("url", "")[:80]))
            if job_id in seen:
                continue
            seen.add(job_id)

            company = item.get("company", item.get("companyName", item.get("employerName", "")))
            if isinstance(company, dict):
                company = company.get("name", "")

            location = item.get("location", item.get("jobLocation", search["location"]))
            description = item.get("description", item.get("jobDescription", ""))
            apply_url = item.get("applyUrl", item.get("url", item.get("jobUrl", "")))
            salary_text = item.get("salary", item.get("salaryText", ""))
            posted_at = item.get("postedAt", item.get("publishedAt", item.get("listedAt", DATE)))

            all_jobs.append({
                "id": f"linkedin-{job_id}",
                "source": "linkedin",
                "title": title.strip(),
                "company": company.strip() if isinstance(company, str) else "",
                "location": location if isinstance(location, str) else str(location),
                "remote": "remote" in str(location).lower() or item.get("workplace", "") == "Remote",
                "salary_text": salary_text if isinstance(salary_text, str) else "",
                "salary_min": None,
                "salary_max": None,
                "posted_date": str(posted_at)[:10] if posted_at else DATE,
                "apply_url": apply_url if isinstance(apply_url, str) else "",
                "description": (description or "")[:2000] if isinstance(description, str) else "",
                "source_query": f"{search['keywords']} | {search['location']}",
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
        print("LinkedIn: APIFY_API_TOKEN not set — no jobs scraped")
        with open(OUT_FILE, "w") as f:
            json.dump([], f)
        return

    jobs = scrape_linkedin(max_results=args.max)

    # Deduplicate
    seen = set()
    unique = [j for j in jobs if j["id"] not in seen and not seen.add(j["id"])]

    with open(OUT_FILE, "w") as f:
        json.dump(unique, f, indent=2)
    print(f"\nLinkedIn: {len(unique)} PM jobs saved to {OUT_FILE}")


if __name__ == "__main__":
    main()
