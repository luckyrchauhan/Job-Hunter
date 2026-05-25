#!/usr/bin/env python3
"""
M2 — Hiring Cafe Scraper
Source: https://hiring.cafe/
Method: Playwright (filters are client-side)

Fetches PM jobs with remote + visa_sponsorship filters.
Outputs: data/jobs-raw/hiring_cafe_YYYY-MM-DD.json

Usage:
  python scripts/scrapers/scrape_hiring_cafe.py
  python scripts/scrapers/scrape_hiring_cafe.py --max 80
  python scripts/scrapers/scrape_hiring_cafe.py --headless false   # debug
"""

import json
import re
import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
RAW_DIR  = BASE_DIR / "data" / "jobs-raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
OUT_FILE = RAW_DIR / f"hiring_cafe_{TODAY}.json"

PM_TITLE_KEYWORDS = [
    "product manager", "product management", "senior pm", "sr pm",
    "associate pm", "apm", "group pm", "staff pm", "principal pm",
    "head of product", "vp product", "director of product",
    "platform pm", "ai pm", "technical pm", "growth pm",
]

def is_pm_title(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in PM_TITLE_KEYWORDS)


def parse_job(hit: dict) -> dict | None:
    """Convert hiring.cafe hit to normalized job record."""
    ji  = hit.get("job_information", {})
    v5  = hit.get("v5_processed_job_data", {})
    title = ji.get("title", "") or v5.get("core_job_title", "")

    if not is_pm_title(title):
        return None

    # Remote filter
    wp_type = v5.get("workplace_type", "")
    remote = wp_type in ("Remote", "Fully Remote", "Flexible Remote")

    # Visa
    visa_flag = v5.get("visa_sponsorship", False)
    visa_status = "confirmed" if visa_flag else "unknown"

    # Salary
    sal_min = v5.get("compensation_min") or v5.get("salary_min")
    sal_max = v5.get("compensation_max") or v5.get("salary_max")
    sal_text = ""
    if sal_min and sal_max:
        sal_text = f"${int(sal_min):,}–${int(sal_max):,}"
    elif sal_min:
        sal_text = f"${int(sal_min):,}+"

    # Company
    company = (
        v5.get("company_name") or
        hit.get("company_name") or
        hit.get("board_token", "").replace("-", " ").title()
    )

    # Location
    location = v5.get("formatted_workplace_location", "")
    if remote:
        location = "remote"

    job_id = f"hiring-cafe-{hit.get('id','')}"

    return {
        "id":           job_id,
        "source":       "hiring_cafe",
        "title":        title,
        "company":      company,
        "location":     location,
        "remote":       remote,
        "salary_text":  sal_text,
        "salary_min":   sal_min,
        "salary_max":   sal_max,
        "apply_url":    hit.get("apply_url", ""),
        "description":  v5.get("requirements_summary", ""),
        "visa_status":  visa_status,
        "sponsorship_confirmed": visa_flag,
        "seniority":    v5.get("seniority_level", ""),
        "job_category": v5.get("job_category", ""),
        "posted_date":  TODAY,
        "scraped_at":   datetime.now(timezone.utc).isoformat(),
        "source_query": "product manager remote visa",
    }


def scrape_via_playwright(max_jobs: int = 100, headless: bool = True) -> list:
    """Use Playwright to load hiring.cafe with PM + remote + visa filters."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("✗ playwright not installed — run: pip install playwright && playwright install chromium")
        return []

    jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Intercept API responses to capture job data
        captured_hits = []

        def handle_response(response):
            url = response.url
            if "_next/data" in url or "hiring.cafe/api" in url:
                try:
                    body = response.json()
                    hits = (
                        body.get("pageProps", {}).get("ssrHits") or
                        body.get("hits") or
                        body.get("jobs") or []
                    )
                    if hits:
                        captured_hits.extend(hits)
                        print(f"  → Captured {len(hits)} jobs from API response")
                except Exception:
                    pass

        page.on("response", handle_response)

        print("Loading hiring.cafe...")
        try:
            page.goto("https://hiring.cafe/", wait_until="networkidle", timeout=30000)
        except PWTimeout:
            print("  ⚠ Page load timeout — continuing with partial load")

        time.sleep(2)

        # Apply "Product Manager" search
        print("Searching for Product Manager...")
        try:
            # Look for search input
            search_selectors = [
                'input[placeholder*="Search"]',
                'input[placeholder*="job"]',
                'input[type="search"]',
                'input[name="q"]',
                '[data-testid="search-input"]',
            ]
            search_box = None
            for sel in search_selectors:
                try:
                    search_box = page.wait_for_selector(sel, timeout=5000)
                    if search_box:
                        break
                except PWTimeout:
                    continue

            if search_box:
                search_box.click()
                search_box.fill("product manager")
                page.keyboard.press("Enter")
                time.sleep(3)
                print("  ✓ Search submitted")
            else:
                print("  ⚠ Search box not found — using URL parameter")
                page.goto("https://hiring.cafe/?q=product+manager", wait_until="networkidle", timeout=20000)
                time.sleep(2)
        except Exception as e:
            print(f"  ⚠ Search error: {e}")

        # Try to enable Remote filter
        print("Applying Remote filter...")
        try:
            remote_selectors = [
                'button:has-text("Remote")',
                '[data-filter="remote"]',
                'label:has-text("Remote")',
                'input[value="remote"]',
            ]
            for sel in remote_selectors:
                try:
                    btn = page.wait_for_selector(sel, timeout=3000)
                    if btn:
                        btn.click()
                        time.sleep(1)
                        print("  ✓ Remote filter applied")
                        break
                except PWTimeout:
                    continue
        except Exception as e:
            print(f"  ⚠ Remote filter: {e}")

        # Try to enable Visa Sponsorship filter
        print("Applying Visa Sponsorship filter...")
        try:
            visa_selectors = [
                'button:has-text("Visa")',
                '[data-filter="visa"]',
                'label:has-text("Visa Sponsorship")',
                'button:has-text("Sponsorship")',
            ]
            for sel in visa_selectors:
                try:
                    btn = page.wait_for_selector(sel, timeout=3000)
                    if btn:
                        btn.click()
                        time.sleep(1)
                        print("  ✓ Visa filter applied")
                        break
                except PWTimeout:
                    continue
        except Exception as e:
            print(f"  ⚠ Visa filter: {e}")

        # Scroll to load more jobs
        print("Loading jobs (scrolling)...")
        prev_count = 0
        scroll_attempts = 0
        max_scrolls = max_jobs // 40 + 2

        while len(captured_hits) < max_jobs and scroll_attempts < max_scrolls:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            scroll_attempts += 1
            if len(captured_hits) == prev_count:
                break
            prev_count = len(captured_hits)
            print(f"  Loaded {len(captured_hits)} job records...")

        # Parse all captured hits
        for hit in captured_hits:
            job = parse_job(hit)
            if job:
                jobs.append(job)
            if len(jobs) >= max_jobs:
                break

        browser.close()

    return jobs


def scrape_via_api_fallback(max_jobs: int = 100) -> list:
    """
    Fallback: fetch SSR data and filter client-side for PM titles.
    Less accurate (no remote/visa filter) but works without Playwright.
    """
    import urllib.request

    print("Using SSR API fallback (no filter support — client-side filter only)...")
    jobs = []

    try:
        # Get buildId
        req = urllib.request.Request(
            "https://hiring.cafe/",
            headers={"User-Agent": "Mozilla/5.0 (compatible; job-hunter/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8")
        build_id = re.search(r'"buildId":"([^"]+)"', html)
        if not build_id:
            print("  ✗ Could not find buildId")
            return []
        build_id = build_id.group(1)
        print(f"  buildId: {build_id}")

        # Fetch SSR data
        url = f"https://hiring.cafe/_next/data/{build_id}/index.json"
        req2 = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; job-hunter/1.0)"}
        )
        with urllib.request.urlopen(req2, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))

        hits = data.get("pageProps", {}).get("ssrHits", [])
        print(f"  Fetched {len(hits)} total jobs from SSR")

        for hit in hits:
            job = parse_job(hit)
            if job:
                jobs.append(job)
            if len(jobs) >= max_jobs:
                break

        print(f"  Filtered to {len(jobs)} PM-matching jobs")

    except Exception as e:
        print(f"  ✗ SSR API error: {e}")

    return jobs


def main():
    parser = argparse.ArgumentParser(description="Scrape hiring.cafe for PM jobs")
    parser.add_argument("--max",      type=int, default=100,  help="Max jobs (default: 100)")
    parser.add_argument("--headless", default="true",         help="Headless browser (default: true)")
    parser.add_argument("--fallback", action="store_true",    help="Use SSR API fallback (no Playwright)")
    args = parser.parse_args()

    headless = args.headless.lower() != "false"

    print(f"Hiring Cafe Scraper — {TODAY}")
    print(f"Output: {OUT_FILE.relative_to(BASE_DIR)}")
    print()

    if args.fallback:
        jobs = scrape_via_api_fallback(args.max)
    else:
        jobs = scrape_via_playwright(args.max, headless)
        if not jobs:
            print("\nPlaywright returned no results — trying SSR fallback...")
            jobs = scrape_via_api_fallback(args.max)

    if not jobs:
        print("✗ No PM jobs found")
        sys.exit(1)

    # Deduplicate by id
    seen = set()
    unique = []
    for j in jobs:
        if j["id"] not in seen:
            seen.add(j["id"])
            unique.append(j)

    with open(OUT_FILE, "w") as f:
        json.dump(unique, f, indent=2)

    print(f"\n✅ Saved {len(unique)} PM jobs → {OUT_FILE.relative_to(BASE_DIR)}")

    # Stats
    remote_count = sum(1 for j in unique if j.get("remote"))
    visa_count   = sum(1 for j in unique if j.get("sponsorship_confirmed"))
    print(f"   Remote: {remote_count} | Visa confirmed: {visa_count}")


if __name__ == "__main__":
    main()
