#!/usr/bin/env python3
"""
Dice.com Scraper — Product Manager roles
Strategy: Apify actor (primary) → Playwright fallback
Saves to: data/jobs-raw/dice-YYYY-MM-DD.json
"""

import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime, date
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
OUT_DIR  = BASE_DIR / "data" / "jobs-raw"
TODAY    = date.today().isoformat()
OUT_FILE = OUT_DIR / f"dice-{TODAY}.json"

APIFY_TOKEN    = os.environ.get("APIFY_API_TOKEN", "")
SEARCH_QUERIES = ["Product Manager", "AI Product Manager"]
LOCATIONS      = ["Boston, MA", "Remote"]


# ── Apify approach ────────────────────────────────────────────────────────────

def scrape_via_apify() -> list:
    """Use Apify web-scraper actor to fetch Dice jobs."""
    if not APIFY_TOKEN:
        return []

    start_urls = []
    for q in SEARCH_QUERIES:
        for loc in LOCATIONS:
            params = urllib.parse.urlencode({"q": q, "location": loc, "filters.postedDate": "ONE_WEEK"})
            start_urls.append({"url": f"https://www.dice.com/jobs?{params}"})

    payload = json.dumps({
        "startUrls": start_urls,
        "maxPagesPerCrawl": 2,
        "pageFunction": """
async function pageFunction(context) {
    const { $ } = context;
    const jobs = [];
    $('dhi-search-card, [data-testid="job-card"]').each((i, el) => {
        const title = $(el).find('[data-testid="job-search-job-detail-link"], .card-title-link').text().trim();
        const company = $(el).find('[data-testid="job-search-company-name"], .card-company').text().trim();
        const location = $(el).find('[data-testid="job-search-location"], .search-result-location').text().trim();
        const url = $(el).find('a[href*="/job-detail/"]').attr('href') || '';
        const posted = $(el).find('[data-testid="job-search-date"], .posted-date').text().trim();
        if (title) jobs.push({ title, company, location, url: url.startsWith('http') ? url : 'https://www.dice.com' + url, posted });
    });
    return jobs;
}
"""
    }).encode()

    try:
        run_url = f"https://api.apify.com/v2/acts/apify~web-scraper/runs?token={APIFY_TOKEN}"
        req = urllib.request.Request(run_url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            run = json.loads(resp.read())
        run_id = run.get("data", {}).get("id", "")
        if not run_id:
            return []

        # Poll for completion
        for _ in range(20):
            time.sleep(6)
            status_url = f"https://api.apify.com/v2/acts/apify~web-scraper/runs/{run_id}?token={APIFY_TOKEN}"
            with urllib.request.urlopen(status_url, timeout=10) as r:
                status = json.loads(r.read()).get("data", {}).get("status", "")
            if status == "SUCCEEDED":
                break
            if status in ("FAILED", "ABORTED"):
                return []

        dataset_id = run.get("data", {}).get("defaultDatasetId", "")
        items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}&format=json"
        with urllib.request.urlopen(items_url, timeout=15) as r:
            items = json.loads(r.read())

        jobs = []
        seen = set()
        for item in items:
            for job in (item if isinstance(item, list) else [item]):
                url = job.get("url", job.get("apply_url", ""))
                if url and url not in seen:
                    seen.add(url)
                    jobs.append({
                        "title":      job.get("title", ""),
                        "company":    job.get("company", ""),
                        "location":   job.get("location", ""),
                        "apply_url":  url,
                        "posted_at":  job.get("posted", ""),
                        "salary_text": job.get("salary", ""),
                        "source":     "Dice",
                        "scraped_at": datetime.now().isoformat(),
                    })
        return jobs
    except Exception as e:
        print(f"  ⚠ Dice Apify error: {e}")
        return []


# ── Playwright fallback ───────────────────────────────────────────────────────

def scrape_via_playwright() -> list:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ⚠ Playwright not installed — pip install playwright && playwright install chromium")
        return []

    jobs = []
    seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0"})

        for q in SEARCH_QUERIES:
            for loc in LOCATIONS:
                try:
                    params = urllib.parse.urlencode({"q": q, "location": loc, "filters.postedDate": "ONE_WEEK"})
                    url = f"https://www.dice.com/jobs?{params}"
                    print(f"    Playwright: {q} / {loc}")
                    page.goto(url, wait_until="networkidle", timeout=20000)
                    page.wait_for_timeout(3000)

                    cards = page.query_selector_all('[role="listitem"] [data-id]')
                    for card in cards:
                        title_el = card.query_selector("a[data-testid='job-search-job-detail-link']")
                        img_el   = card.query_selector("img")

                        title     = title_el.inner_text().strip() if title_el else ""
                        company   = (img_el.get_attribute("alt") or "").strip() if img_el else ""
                        location  = loc
                        href      = title_el.get_attribute("href") if title_el else ""
                        apply_url = href if href.startswith("http") else f"https://www.dice.com{href}"

                        if title and apply_url not in seen:
                            seen.add(apply_url)
                            jobs.append({
                                "title":      title,
                                "company":    company,
                                "location":   location,
                                "apply_url":  apply_url,
                                "source":     "Dice",
                                "scraped_at": datetime.now().isoformat(),
                            })
                except Exception as e:
                    print(f"    ⚠ Playwright Dice error ({q}/{loc}): {e}")

        browser.close()
    return jobs


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("  Trying Apify...")
    jobs = scrape_via_apify()

    if not jobs:
        print("  Apify unavailable — trying Playwright...")
        jobs = scrape_via_playwright()

    OUT_FILE.write_text(json.dumps(jobs, indent=2))
    print(f"\nDice: {len(jobs)} PM jobs saved to {OUT_FILE.name}")


if __name__ == "__main__":
    # Load .env
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
    main()
