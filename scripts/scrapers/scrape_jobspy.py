#!/usr/bin/env python3
"""
JobSpy scraper — replaces Apify for Indeed, Glassdoor, ZipRecruiter
Uses python-jobspy (no API key, no cost limit)

Sources: indeed, glassdoor, zip_recruiter
LinkedIn intentionally excluded (CLAUDE.md: LinkedIn = Playwright only)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from jobspy import scrape_jobs
except ImportError:
    print("❌ python-jobspy not installed. Run: pip install python-jobspy markdownify regex")
    sys.exit(1)

BASE_DIR = Path(__file__).parent.parent.parent
RAW_DIR = BASE_DIR / "data" / "jobs-raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

TODAY = datetime.now().strftime("%Y-%m-%d")
SCRAPED_AT = datetime.now(timezone.utc).isoformat()

SEARCHES = [
    ("product manager", "Remote, USA"),
    ("AI product manager", "Remote, USA"),
    ("platform product manager", "Remote, USA"),
    ("technical product manager", "Remote, USA"),
    ("product manager", "Boston, MA"),
]

SOURCES = ["indeed", "glassdoor", "zip_recruiter"]


def normalize_job(row, source: str) -> dict:
    """Convert JobSpy DataFrame row → our standard job dict."""
    def _safe_int(v):
        try:
            f = float(v)
            return int(f) if f == f else None  # f != f means NaN
        except (TypeError, ValueError):
            return None

    salary_min = _safe_int(row.get("min_amount"))
    salary_max = _safe_int(row.get("max_amount"))

    # Build salary text
    if salary_min and salary_max:
        salary_text = f"${salary_min:,} – ${salary_max:,}"
    elif salary_min:
        salary_text = f"${salary_min:,}+"
    else:
        salary_text = ""

    loc = str(row.get("location") or "")
    is_remote = (
        row.get("is_remote") is True
        or "remote" in loc.lower()
        or "anywhere" in loc.lower()
    )

    return {
        "id": str(row.get("id") or ""),
        "title": str(row.get("title") or ""),
        "company": str(row.get("company") or ""),
        "location": loc,
        "remote": is_remote,
        "description": str(row.get("description") or ""),
        "salary_min": int(salary_min) if salary_min else None,
        "salary_max": int(salary_max) if salary_max else None,
        "salary_text": salary_text,
        "posted_date": str(row.get("date_posted") or "")[:10] or TODAY,
        "apply_url": str(row.get("job_url") or row.get("job_url_direct") or ""),
        "source": source,
        "scraped_at": SCRAPED_AT,
    }


def is_pm_title(title: str) -> bool:
    title_l = title.lower()
    pm_terms = ["product manager", "pm ", " pm,", "product lead", "ai pm"]
    exclude = ["senior product manager", "sr product manager", "principal product",
               "director of product", "vp of product", "head of product",
               "group product manager", "software engineer", "data engineer",
               "data scientist", "sales", "recruiter", "marketing", "designer"]
    if any(e in title_l for e in exclude):
        return False
    return any(p in title_l for p in pm_terms)


def scrape_source(source: str) -> list:
    seen_ids = set()
    jobs = []

    for search_term, location in SEARCHES:
        print(f"  [{source}] '{search_term}' @ '{location}'")
        try:
            df = scrape_jobs(
                site_name=[source],
                search_term=search_term,
                location=location,
                results_wanted=25,
                hours_old=336,  # 14 days
                country_indeed="USA",
            )
            if df is None or len(df) == 0:
                print(f"    → 0 results")
                continue

            count = 0
            for _, row in df.iterrows():
                job = normalize_job(row.to_dict(), source)
                if not is_pm_title(job["title"]):
                    continue
                uid = job["id"] or f"{job['company']}|{job['title']}|{job['location']}"
                if uid in seen_ids:
                    continue
                seen_ids.add(uid)
                jobs.append(job)
                count += 1

            print(f"    → {count} PM jobs")

        except Exception as e:
            print(f"    ❌ Error: {e}")

    return jobs


def main():
    print(f"JobSpy scraper — {TODAY}")
    print(f"Sources: {', '.join(SOURCES)}\n")

    all_jobs = []
    for source in SOURCES:
        jobs = scrape_source(source)
        all_jobs.extend(jobs)
        outfile = RAW_DIR / f"{source.replace('_', '')}-jobspy-{TODAY}.json"
        with open(outfile, "w") as f:
            json.dump(jobs, f, indent=2)
        print(f"  ✅ {source}: {len(jobs)} jobs → {outfile.name}\n")

    print(f"Total: {len(all_jobs)} PM jobs across {len(SOURCES)} sources")


if __name__ == "__main__":
    main()
