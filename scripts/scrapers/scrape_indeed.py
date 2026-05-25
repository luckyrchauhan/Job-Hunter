"""
Indeed Job Scraper — Playwright (handles JS/bot protection)
Saves to: data/jobs-raw/indeed-YYYY-MM-DD.json
"""
import os, json, time, asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"data/jobs-raw/indeed-{DATE}.json"

SEARCHES = [
    {"q": "product+manager", "l": "remote"},
    {"q": "senior+product+manager", "l": "remote"},
    {"q": "AI+product+manager", "l": "remote"},
    {"q": "product+manager", "l": "Boston%2C+MA"},
    {"q": "technical+product+manager", "l": "remote"},
]

PM_TITLES = [
    "product manager", "senior product manager", "sr. product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager"
]

def is_pm_title(title):
    t = title.lower()
    return any(pm in t for pm in PM_TITLES)

async def scrape_search(page, q, l):
    url = f"https://www.indeed.com/jobs?q={q}&l={l}&fromage=7&sort=date"
    jobs = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        cards = await page.query_selector_all('[data-jk]')
        print(f"    Found {len(cards)} cards")

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
                "salary_min": None,
                "salary_max": None,
                "posted_date": DATE,
                "apply_url": f"https://www.indeed.com/viewjob?jk={job_key}",
                "description": "",
                "source_query": f"{q} | {l}",
                "scraped_at": datetime.now().isoformat(),
            })
    except Exception as e:
        print(f"    Error: {e}")
    return jobs

async def main():
    os.makedirs("data/jobs-raw", exist_ok=True)
    all_jobs = []
    seen_ids = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for search in SEARCHES:
            q, l = search["q"], search["l"]
            print(f"  Searching: '{q}' in '{l}'")
            jobs = await scrape_search(page, q, l)
            for j in jobs:
                if j["id"] not in seen_ids:
                    seen_ids.add(j["id"])
                    all_jobs.append(j)
            print(f"    → {len(all_jobs)} total unique PM jobs so far")
            await asyncio.sleep(3)

        await browser.close()

    with open(OUT_FILE, "w") as f:
        json.dump(all_jobs, f, indent=2)
    print(f"\nIndeed: {len(all_jobs)} PM jobs saved to {OUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
