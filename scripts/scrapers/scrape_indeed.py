"""
Indeed Job Scraper
Primary: Apify actor valig/indeed-jobs-scraper (company name in employer.name)
Fallback: Playwright (slower, bot-protected)
Saves to: data/jobs-raw/indeed-YYYY-MM-DD.json

Usage:
  python scripts/scrapers/scrape_indeed.py
  python scripts/scrapers/scrape_indeed.py --playwright   # force Playwright
  python scripts/scrapers/scrape_indeed.py --max 100

Requires: APIFY_API_TOKEN in .env for Apify mode
"""
import os, json, time, asyncio, argparse
from datetime import datetime
from pathlib import Path
import requests
from dotenv import load_dotenv
load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"data/jobs-raw/indeed-{DATE}.json"
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN", "")

SEARCHES = [
    {"position": "product manager", "location": "Remote, USA"},
    {"position": "senior product manager", "location": "Remote, USA"},
    {"position": "AI product manager", "location": "Remote, USA"},
    {"position": "technical product manager", "location": "Remote, USA"},
    {"position": "product manager", "location": "Boston, MA"},
]

PM_TITLES = [
    "product manager", "senior product manager", "sr. product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "head of product", "director of product", "vp of product",
]

def is_pm_title(title: str) -> bool:
    t = title.lower()
    return any(pm in t for pm in PM_TITLES)


# ─── Apify Primary ─────────────────────────────────────────────────────────────

def scrape_apify(max_results: int = 50) -> list:
    """
    Use Apify actor valig/indeed-jobs-scraper.
    Company name comes from employer.name (not JS-rendered, reliable).
    """
    if not APIFY_TOKEN:
        print("  ⚠ APIFY_API_TOKEN not set — skipping Apify")
        return []

    actor_id = "valig~indeed-jobs-scraper"
    base_url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"

    all_jobs = []
    seen = set()

    for search in SEARCHES:
        print(f"  Apify Indeed: '{search['position']}' @ '{search['location']}'")
        payload = {
            "position": search["position"],
            "location": search["location"],
            "maxItems": max_results,
            "parseCompanyDetails": True,
            "saveOnlyUniqueItems": True,
            "followApplyRedirects": False,
        }

        try:
            resp = requests.post(
                base_url,
                params={"token": APIFY_TOKEN, "timeout": 120, "memory": 512},
                json=payload,
                timeout=150,
            )
            if resp.status_code not in (200, 201):
                print(f"    Apify HTTP {resp.status_code}: {resp.text[:200]}")
                continue

            items = resp.json() if isinstance(resp.json(), list) else resp.json().get("items", [])
            print(f"    → {len(items)} raw items")

            for item in items:
                title = item.get("positionName", item.get("title", ""))
                if not title or not is_pm_title(title):
                    continue

                job_id = item.get("id", item.get("jobKey", ""))
                if job_id in seen:
                    continue
                seen.add(job_id)

                # Company: Apify actor provides employer object with .name
                employer = item.get("employer") or {}
                company = (employer.get("name") or
                           item.get("company", item.get("companyName", "")))

                salary_text = item.get("salary", item.get("salaryText", ""))

                all_jobs.append({
                    "id": f"indeed-{job_id}",
                    "source": "indeed",
                    "title": title.strip(),
                    "company": company.strip() if company else "",
                    "location": item.get("location", search["location"]),
                    "remote": "remote" in item.get("location", "").lower() or
                              item.get("remote", False),
                    "salary_text": salary_text,
                    "salary_min": None,
                    "salary_max": None,
                    "posted_date": item.get("postedAt", DATE)[:10] if item.get("postedAt") else DATE,
                    "apply_url": item.get("url", item.get("applyUrl", "")),
                    "description": (item.get("description") or item.get("jobDescription") or "")[:2000],
                    "source_query": f"{search['position']} | {search['location']}",
                    "scraped_at": datetime.now().isoformat(),
                })

        except requests.Timeout:
            print(f"    Apify timeout for '{search['position']}' — skipping")
        except Exception as e:
            print(f"    Apify error: {e}")

        time.sleep(2)

    return all_jobs


# ─── Playwright Fallback ───────────────────────────────────────────────────────

async def scrape_playwright_search(page, q: str, l: str) -> list:
    import random
    url = f"https://www.indeed.com/jobs?q={q}&l={l}&fromage=7&sort=date"
    jobs = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(3, 7))  # random delay to reduce bot detection

        cards = await page.query_selector_all('[data-jk]')
        print(f"    Playwright: {len(cards)} cards for '{q}'")

        for card in cards:
            job_key = await card.get_attribute("data-jk") or ""
            title_el = await card.query_selector("span[title]")
            company_el = await card.query_selector('[data-testid="company-name"]')
            location_el = await card.query_selector('[data-testid="text-location"]')
            salary_el = await card.query_selector('[data-testid="attribute_snippet_testid"]')

            title = ""
            if title_el:
                title = await title_el.get_attribute("title") or await title_el.inner_text()
            if not title or not is_pm_title(title):
                continue

            company = await company_el.inner_text() if company_el else ""
            location = await location_el.inner_text() if location_el else l
            salary = await salary_el.inner_text() if salary_el else ""

            jobs.append({
                "id": f"indeed-{job_key}",
                "source": "indeed",
                "title": title.strip(),
                "company": company.strip(),
                "location": location.strip(),
                "remote": "remote" in location.lower(),
                "salary_text": salary.strip(),
                "salary_min": None, "salary_max": None,
                "posted_date": DATE,
                "apply_url": f"https://www.indeed.com/viewjob?jk={job_key}",
                "description": "",
                "source_query": f"{q} | {l}",
                "scraped_at": datetime.now().isoformat(),
            })
    except Exception as e:
        print(f"    Playwright error for '{q}': {e}")
    return jobs


async def scrape_playwright() -> list:
    from playwright.async_api import async_playwright
    import random

    all_jobs = []
    seen_ids = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        for search in SEARCHES[:3]:  # limit to 3 queries to reduce bot detection
            q = search["position"].replace(" ", "+")
            l = search["location"].replace(", ", "%2C+")
            jobs = await scrape_playwright_search(page, q, l)
            for j in jobs:
                if j["id"] not in seen_ids:
                    seen_ids.add(j["id"])
                    all_jobs.append(j)
            await asyncio.sleep(random.uniform(5, 10))

        await browser.close()

    return all_jobs


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--playwright", action="store_true", help="Force Playwright fallback")
    parser.add_argument("--max", type=int, default=50, help="Max results per query (Apify)")
    args = parser.parse_args()

    os.makedirs("data/jobs-raw", exist_ok=True)

    jobs = []
    if not args.playwright and APIFY_TOKEN:
        print("  Using Apify (primary)...")
        jobs = scrape_apify(max_results=args.max)

    if not jobs:
        if not APIFY_TOKEN and not args.playwright:
            print("  ⚠ APIFY_API_TOKEN not set — falling back to Playwright")
        else:
            print("  Apify returned 0 results — falling back to Playwright")
        jobs = asyncio.run(scrape_playwright())

    # Deduplicate
    seen = set()
    unique = []
    for j in jobs:
        if j["id"] not in seen:
            seen.add(j["id"])
            unique.append(j)

    with open(OUT_FILE, "w") as f:
        json.dump(unique, f, indent=2)
    print(f"\nIndeed: {len(unique)} PM jobs saved to {OUT_FILE}")


if __name__ == "__main__":
    main()
