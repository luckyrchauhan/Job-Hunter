"""
ZipRecruiter Job Scraper
Primary:    Apify actor bkwSYfgLsyEazgOvf (URL-based, full description + salary)
Fallback 1: JobSpy (python-jobspy, free, no key)
Saves to: data/jobs-raw/ziprecruiter-YYYY-MM-DD.json

Usage:
  python scripts/scrapers/scrape_ziprecruiter.py
  python scripts/scrapers/scrape_ziprecruiter.py --max 100
"""
import os, json, time, re, argparse
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import urllib.request

load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = Path(f"data/jobs-raw/ziprecruiter-{DATE}.json")
APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
ACTOR_ID = "bkwSYfgLsyEazgOvf"  # Ziprecruiter Jobs Scraper (900+ runs, URL-based)

SEARCH_QUERIES = [
    "product manager",
    "senior product manager",
    "AI product manager",
    "platform product manager",
]

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

def parse_salary(text: str):
    if not text:
        return None, None
    text = str(text).replace("K", "000").replace("k", "000")
    nums = re.findall(r"[\d,]+", text)
    nums = [int(n.replace(",", "")) for n in nums if int(n.replace(",", "")) > 10000]
    if len(nums) >= 2:
        return min(nums), max(nums)
    elif len(nums) == 1:
        return nums[0], nums[0]
    return None, None

def parse_posted(text: str) -> str:
    text = (text or "").lower().strip()
    today = datetime.now().date()
    if "today" in text or "hour" in text or "just" in text:
        return str(today)
    m = re.search(r"(\d+)\s*day", text)
    if m:
        return str(today - timedelta(days=int(m.group(1))))
    m = re.search(r"(\d+)\s*week", text)
    if m:
        return str(today - timedelta(weeks=int(m.group(1))))
    return str(today)

def apify_run(search_url: str, max_items: int) -> list:
    payload = json.dumps({
        "startUrls": [{"url": search_url}],
        "maxItems": max_items,
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
    # Fields: job_title, company_name, location, salary, date, URL, description
    title = item.get("job_title", "") or ""
    company = item.get("company_name", "") or ""
    location = item.get("location", "") or ""
    salary_text = str(item.get("salary", "") or "")
    description = item.get("description", "") or ""
    posted_raw = item.get("date", "") or ""
    url = item.get("URL", "") or ""

    salary_min, salary_max = parse_salary(salary_text)
    remote = "remote" in location.lower() or "remote" in description.lower()[:200]
    posted = parse_posted(posted_raw)

    return {
        "id": f"ziprecruiter-{hash(url) % 10**10}",
        "source": "ziprecruiter",
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
        "source_query": query,
        "scraped_at": datetime.now().isoformat(),
    }

def scrape_jobspy_zip() -> list:
    """JobSpy fallback for ZipRecruiter — free, no key."""
    try:
        from jobspy import scrape_jobs
    except ImportError:
        print("  ⚠ python-jobspy not installed — skipping JobSpy fallback")
        return []

    def _safe_int(v):
        try:
            f = float(v)
            return int(f) if f == f else None
        except (TypeError, ValueError):
            return None

    all_jobs, seen = [], set()
    for query in SEARCH_QUERIES:
        try:
            df = scrape_jobs(
                site_name=["zip_recruiter"],
                search_term=query,
                location="Remote, USA",
                results_wanted=25,
                hours_old=336,
            )
            if df is None or len(df) == 0:
                continue
            for _, row in df.iterrows():
                r = row.to_dict()
                title = str(r.get("title") or "")
                if not is_pm_title(title):
                    continue
                uid = str(r.get("id") or f"{r.get('company')}|{title}")
                if uid in seen:
                    continue
                seen.add(uid)
                sal_min = _safe_int(r.get("min_amount"))
                sal_max = _safe_int(r.get("max_amount"))
                loc = str(r.get("location") or "Remote")
                all_jobs.append({
                    "id": f"zip-jobspy-{uid}",
                    "source": "ziprecruiter",
                    "title": title.strip(),
                    "company": str(r.get("company") or "").strip(),
                    "location": loc,
                    "remote": r.get("is_remote") is True or "remote" in loc.lower(),
                    "description": str(r.get("description") or ""),
                    "salary_min": sal_min,
                    "salary_max": sal_max,
                    "salary_text": f"${sal_min:,}–${sal_max:,}" if sal_min and sal_max else "",
                    "posted_date": str(r.get("date_posted") or DATE)[:10],
                    "apply_url": str(r.get("job_url") or ""),
                    "scraped_at": datetime.now().isoformat(),
                })
        except Exception as e:
            print(f"  ⚠ JobSpy zip error for '{query}': {e}")
    return all_jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=100)
    args = parser.parse_args()

    Path("data/jobs-raw").mkdir(parents=True, exist_ok=True)

    # Tier 1: Apify (primary)
    all_jobs, seen_ids = [], set()
    if APIFY_TOKEN:
        print("ZipRecruiter scraper — Apify actor")
        per_query = max(20, args.max // len(SEARCH_QUERIES))
        for query in SEARCH_QUERIES:
            search_url = f"https://www.ziprecruiter.com/candidate/search?search={query.replace(' ','+')}&location=Remote&days=7"
            print(f"  '{query}' (max {per_query})")
            items = apify_run(search_url, per_query)
            count = 0
            for item in items:
                job = normalize(item, query)
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

    # Tier 2: JobSpy fallback
    if not all_jobs:
        print("  Apify returned 0 — falling back to JobSpy...")
        all_jobs = scrape_jobspy_zip()
        if all_jobs:
            print(f"  JobSpy recovered {len(all_jobs)} jobs")
        else:
            print("  JobSpy also 0 (ZipRecruiter Cloudflare blocks all scrapers)")

    OUT_FILE.write_text(json.dumps(all_jobs, indent=2))
    salary_count = sum(1 for j in all_jobs if j.get("salary_text"))
    print(f"\nZipRecruiter: {len(all_jobs)} PM jobs → {OUT_FILE}")
    print(f"  With salary: {salary_count} | With description: {sum(1 for j in all_jobs if j.get('description'))}")

if __name__ == "__main__":
    main()
