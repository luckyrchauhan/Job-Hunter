#!/usr/bin/env python3
"""
Monster.com Scraper — Product Manager roles
Strategy: Apify actor (Monster blocks headless browsers directly)
Requires: APIFY_API_TOKEN in .env
Saves to: data/jobs-raw/monster-YYYY-MM-DD.json
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
OUT_FILE = OUT_DIR / f"monster-{TODAY}.json"

APIFY_TOKEN    = os.environ.get("APIFY_API_TOKEN", "")
SEARCH_QUERIES = ["Product Manager", "AI Product Manager"]
LOCATIONS      = ["Boston, MA", "Remote"]


def scrape_via_apify() -> list:
    """Use Apify cheerio-scraper to get Monster jobs (bypasses bot protection)."""
    if not APIFY_TOKEN:
        print("  ⚠ Monster: APIFY_API_TOKEN not set — skipping")
        return []

    start_urls = []
    for q in SEARCH_QUERIES:
        for loc in LOCATIONS:
            params = urllib.parse.urlencode({"q": q, "where": loc})
            start_urls.append({"url": f"https://www.monster.com/jobs/search?{params}"})

    payload = json.dumps({
        "startUrls": start_urls,
        "maxPagesPerCrawl": 2,
        "pageFunction": """
async function pageFunction(context) {
    const { $ } = context;
    const jobs = [];
    $('article[data-jobid], [class*="JobCard"], .job-cardstyle__JobCardComponent').each((i, el) => {
        const title = $(el).find('h2 a, [data-testid="job-title"], .title a').first().text().trim();
        const company = $(el).find('[data-testid="company-name"], .company-name, .name').first().text().trim();
        const location = $(el).find('[data-testid="job-location"], .location').first().text().trim();
        const href = $(el).find('a[href*="job-openings"], h2 a').first().attr('href') || '';
        const url = href.startsWith('http') ? href : 'https://www.monster.com' + href;
        if (title) jobs.push({ title, company, location, url });
    });
    return jobs;
}
"""
    }).encode()

    try:
        run_url = f"https://api.apify.com/v2/acts/apify~cheerio-scraper/runs?token={APIFY_TOKEN}"
        req = urllib.request.Request(run_url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            run = json.loads(resp.read())
        run_id = run.get("data", {}).get("id", "")
        if not run_id:
            print("  ⚠ Monster Apify: no run ID returned")
            return []

        print(f"  Monster Apify run started: {run_id}")
        for _ in range(20):
            time.sleep(8)
            status_url = f"https://api.apify.com/v2/acts/apify~cheerio-scraper/runs/{run_id}?token={APIFY_TOKEN}"
            with urllib.request.urlopen(status_url, timeout=10) as r:
                status = json.loads(r.read()).get("data", {}).get("status", "")
            print(f"    Status: {status}")
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
                url = job.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    jobs.append({
                        "title":      job.get("title", ""),
                        "company":    job.get("company", ""),
                        "location":   job.get("location", ""),
                        "apply_url":  url,
                        "source":     "Monster",
                        "scraped_at": datetime.now().isoformat(),
                    })
        return jobs
    except Exception as e:
        print(f"  ⚠ Monster Apify error: {e}")
        return []


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not APIFY_TOKEN:
        print("Monster: APIFY_API_TOKEN required — set in .env to enable Monster scraping")
        OUT_FILE.write_text("[]")
        return

    jobs = scrape_via_apify()
    OUT_FILE.write_text(json.dumps(jobs, indent=2))
    print(f"\nMonster: {len(jobs)} PM jobs saved to {OUT_FILE.name}")


if __name__ == "__main__":
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
    main()
