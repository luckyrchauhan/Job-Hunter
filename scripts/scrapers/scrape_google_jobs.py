"""
Google Jobs Scraper
Primary:    Apify actor CkLDY9GAQf6QlP6GP (25k+ runs, full JD + salary)
Fallback 1: SerpAPI Google Jobs endpoint (100 free searches/month, SERPAPI_API_KEY in .env)
Returns: full job description, salary, company, location from Google Jobs aggregator
Saves to: data/jobs-raw/google_jobs-YYYY-MM-DD.json

Google Jobs aggregates LinkedIn, Indeed, Glassdoor, company sites — unique coverage.

Usage:
  python scripts/scrapers/scrape_google_jobs.py
  python scripts/scrapers/scrape_google_jobs.py --max 100
"""
import os, json, time, re, argparse
import urllib.request, urllib.parse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = Path(f"data/jobs-raw/google_jobs-{DATE}.json")
APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
SERPAPI_KEY = os.environ.get("SERPAPI_API_KEY", "")
ACTOR_ID = "CkLDY9GAQf6QlP6GP"  # Google Jobs Scraper (25k+ runs)

# Apify uses all queries (no cost limit beyond monthly compute)
SEARCH_QUERIES = [
    "product manager remote USA",
    "senior product manager remote",
    "AI product manager USA",
    "platform product manager remote",
    "technical product manager USA",
]

# SerpAPI uses only these 2 — conserves free tier (100/mo limit)
# 2 queries × 1 run/day × 30 days = 60/month (40 buffer)
SERPAPI_QUERIES = [
    "product manager remote USA",   # broadest, highest yield
    "AI product manager",           # your differentiator
]
SERPAPI_MAX_PER_QUERY = 10  # 2 queries × 10 = 20 results/day max

PM_TITLES = [
    "product manager", "senior product manager", "sr. product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "group product manager", "head of product",
]
EXCLUDE_TITLES = [
    "marketing manager", "sales manager", "account manager", "recruiter",
    "software engineer", "developer", "designer", "data scientist",
    "director of", "vp of", "vice president", "chief ",
]

def is_pm_title(title: str) -> bool:
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_TITLES):
        return False
    return any(pm in t for pm in PM_TITLES)

def parse_salary(extensions: list) -> tuple:
    """Google Jobs puts salary in extensions list."""
    if not extensions:
        return "", None, None
    for ext in extensions:
        ext_str = str(ext)
        if "$" in ext_str or "salary" in ext_str.lower() or "hour" in ext_str.lower():
            # Parse numbers
            text = ext_str.replace("K", "000").replace("k", "000")
            nums = re.findall(r"[\d,]+", text)
            nums = [int(n.replace(",", "")) for n in nums if int(n.replace(",", "")) > 10000]
            if nums:
                s_min = min(nums)
                s_max = max(nums)
                # Hourly to annual
                if "hour" in ext_str.lower():
                    s_min = s_min * 2080
                    s_max = s_max * 2080
                return ext_str, s_min, s_max
    return "", None, None

def parse_posted(detected: dict) -> str:
    """Parse posted date from detected_extensions dict."""
    today = datetime.now().date()
    posted_raw = detected.get("posted_at", "") or ""
    if not posted_raw:
        return str(today)
    posted_raw = posted_raw.lower()
    if "today" in posted_raw or "hour" in posted_raw or "just" in posted_raw:
        return str(today)
    m = re.search(r"(\d+)\s*day", posted_raw)
    if m:
        from datetime import timedelta
        return str(today - timedelta(days=int(m.group(1))))
    m = re.search(r"(\d+)\s*week", posted_raw)
    if m:
        from datetime import timedelta
        return str(today - timedelta(weeks=int(m.group(1))))
    return str(today)

def apify_run(query: str, max_items: int) -> list:
    payload = json.dumps({
        "query": query,
        "maxResults": max_items,
        "datePosted": "week",         # past week only
        "language": "en",
    }).encode()

    req = urllib.request.Request(
        f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs?token={APIFY_TOKEN}",
        data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            run_data = json.loads(r.read())
    except Exception as e:
        print(f"    Start error: {e}")
        return []

    run_id = run_data.get("data", {}).get("id", "")
    if not run_id:
        return []

    for _ in range(40):
        time.sleep(6)
        try:
            with urllib.request.urlopen(
                f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}", timeout=10
            ) as r:
                s = json.loads(r.read())
            status = s["data"]["status"]
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
        except Exception:
            continue

    if status != "SUCCEEDED":
        print(f"    Run {status}")
        return []

    dataset_id = s["data"]["defaultDatasetId"]
    try:
        with urllib.request.urlopen(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}&clean=true&limit={max_items}",
            timeout=20
        ) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"    Dataset error: {e}")
        return []

def normalize(item: dict, query: str) -> dict:
    # Fields: title, company_name, location, via, share_link, extensions,
    #         detected_extensions, source_link, job_title, description
    title = item.get("title", item.get("job_title", "")) or ""
    company = item.get("company_name", "") or ""
    location = item.get("location", "") or ""
    description = item.get("description", "") or ""
    extensions = item.get("extensions", []) or []
    detected = item.get("detected_extensions", {}) or {}
    url = item.get("share_link", item.get("source_link", "")) or ""

    salary_text, salary_min, salary_max = parse_salary(extensions)
    posted = parse_posted(detected)
    remote = (
        "remote" in location.lower() or
        detected.get("work_from_home", False) or
        "remote" in description.lower()[:300]
    )

    # Only recent (14 days)
    try:
        from datetime import datetime as dt, timedelta
        days_old = (dt.now().date() - dt.strptime(posted, "%Y-%m-%d").date()).days
        if days_old > 14:
            return None
    except Exception:
        pass

    return {
        "id": f"google-jobs-{hash(url or title + company) % 10**10}",
        "source": "google_jobs",
        "title": title.strip(),
        "company": company.strip(),
        "location": location.strip(),
        "remote": remote,
        "salary_text": salary_text.strip(),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "posted_date": posted,
        "apply_url": url,
        "description": description[:6000],
        "via": item.get("via", ""),      # which platform (LinkedIn, Indeed, etc.)
        "source_query": query,
        "scraped_at": datetime.now().isoformat(),
    }

def scrape_serpapi(max_per_query: int = 20) -> list:
    """
    SerpAPI fallback — Google Jobs endpoint.
    Free tier: 100 searches/month. No credit card needed for free plan.
    Sign up: https://serpapi.com/
    Set SERPAPI_API_KEY in .env
    """
    if not SERPAPI_KEY:
        print("  ⚠ SERPAPI_API_KEY not set — skipping SerpAPI fallback")
        print("     Get free key (100/mo): https://serpapi.com/")
        return []

    all_jobs, seen = [], set()

    for query in SERPAPI_QUERIES:
        print(f"  SerpAPI: '{query}' (max {SERPAPI_MAX_PER_QUERY})")
        try:
            params = urllib.parse.urlencode({
                "engine": "google_jobs",
                "q": query,
                "api_key": SERPAPI_KEY,
                "chips": "date_posted:week",
                "ltype": "1",   # remote
                "num": SERPAPI_MAX_PER_QUERY,
            })
            url = f"https://serpapi.com/search?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())

            results = data.get("jobs_results", [])
            count = 0
            for item in results:
                title = item.get("title", "") or ""
                if not is_pm_title(title):
                    continue
                company = item.get("company_name", "") or ""
                location = item.get("location", "") or ""
                description = item.get("description", "") or ""
                url_val = item.get("share_link", "") or ""
                uid = f"serpapi-{hash(url_val or title + company) % 10**10}"
                if uid in seen:
                    continue
                seen.add(uid)

                # Extract salary from extensions
                extensions = item.get("extensions", []) or []
                salary_text = next((e for e in extensions if "$" in e or "salary" in e.lower()), "")

                # Parse posted date from detected_extensions
                detected = item.get("detected_extensions", {}) or {}
                posted = DATE
                if detected.get("posted_at"):
                    posted = detected["posted_at"]

                all_jobs.append({
                    "id": uid,
                    "source": "google_jobs",
                    "title": title.strip(),
                    "company": company.strip(),
                    "location": location.strip(),
                    "remote": "remote" in location.lower() or detected.get("work_from_home", False),
                    "description": description,
                    "salary_text": salary_text,
                    "salary_min": None,
                    "salary_max": None,
                    "posted_date": posted[:10],
                    "apply_url": url_val,
                    "via": item.get("via", ""),
                    "source_method": "serpapi",
                    "scraped_at": datetime.now().isoformat(),
                })
                count += 1

            print(f"    → {count} PM jobs")
            time.sleep(1)  # SerpAPI rate limit courtesy

        except Exception as e:
            print(f"    SerpAPI error: {e}")

    return all_jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=100)
    args = parser.parse_args()

    Path("data/jobs-raw").mkdir(parents=True, exist_ok=True)

    # Tier 1: Apify (primary — full JD + salary)
    all_jobs, seen_ids = [], set()
    if APIFY_TOKEN:
        print("Google Jobs scraper — Apify actor (aggregates LinkedIn/Indeed/Glassdoor/company sites)")
        per_query = max(20, args.max // len(SEARCH_QUERIES))
        for query in SEARCH_QUERIES:
            print(f"  '{query}' (max {per_query})")
            items = apify_run(query, per_query)
            count = 0
            for item in items:
                job = normalize(item, query)
                if not job:
                    continue
                if not is_pm_title(job["title"]):
                    continue
                if job["id"] in seen_ids:
                    continue
                seen_ids.add(job["id"])
                all_jobs.append(job)
                count += 1
            print(f"    → {count} PM jobs")
    else:
        print("  ⚠ APIFY_API_TOKEN not set — skipping Apify")

    # Tier 2: SerpAPI fallback
    if not all_jobs:
        print("  Apify returned 0 — falling back to SerpAPI...")
        all_jobs = scrape_serpapi(max_per_query=20)
        if all_jobs:
            print(f"  SerpAPI recovered {len(all_jobs)} jobs")
        elif not SERPAPI_KEY:
            print("  ⚠ Set SERPAPI_API_KEY in .env for Google Jobs fallback (free 100/mo)")

    OUT_FILE.write_text(json.dumps(all_jobs, indent=2))
    salary_count = sum(1 for j in all_jobs if j.get("salary_text"))
    desc_count = sum(1 for j in all_jobs if j.get("description"))
    print(f"\nGoogle Jobs: {len(all_jobs)} PM jobs → {OUT_FILE}")
    print(f"  With salary: {salary_count} | With description: {desc_count}")

if __name__ == "__main__":
    main()
