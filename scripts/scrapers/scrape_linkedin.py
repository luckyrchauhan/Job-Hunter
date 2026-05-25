"""
LinkedIn Job Scraper
Method: Playwright — LinkedIn public job search pages (no login needed)
URL: /jobs/search/?keywords=...&f_WT=2 (remote) &f_TPR=r604800 (past week)
Saves to: data/jobs-raw/linkedin-YYYY-MM-DD.json

Usage:
  python scripts/scrapers/scrape_linkedin.py
  python scripts/scrapers/scrape_linkedin.py --max 200
  python scripts/scrapers/scrape_linkedin.py --headless false  # debug
"""
import os, json, asyncio, argparse
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"data/jobs-raw/linkedin-{DATE}.json"

PM_TITLES = [
    "product manager", "senior product manager", "sr. product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "head of product", "director of product", "vp of product",
    "group product manager",
]

SEARCH_QUERIES = [
    "product manager",
    "senior product manager",
    "AI product manager",
    "platform product manager",
]

def is_pm_title(title: str) -> bool:
    t = title.lower()
    return any(pm in t for pm in PM_TITLES)


async def scrape_query(page, keywords: str, max_per_query: int) -> list:
    """Scrape one LinkedIn search query, scrolling to load more results."""
    jobs = []
    seen_urls = set()

    # LinkedIn remote (f_WT=2) + past week (f_TPR=r604800) + US
    url = (f"https://www.linkedin.com/jobs/search/"
           f"?keywords={keywords.replace(' ', '+')}"
           f"&location=United+States&f_WT=2&f_TPR=r604800"
           f"&position=1&pageNum=0")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Scroll to load more job cards (LinkedIn lazy-loads)
        loaded = 0
        for _ in range(max(1, max_per_query // 25)):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.5)

            # Click "Show more" button if present
            try:
                btn = await page.query_selector("button.infinite-scroller__show-more-button")
                if btn:
                    await btn.click()
                    await asyncio.sleep(1.5)
            except Exception:
                pass

        cards = await page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('.job-search-card, [class*="job-card-container"], [data-entity-urn*="jobPosting"]').forEach(card => {
                const titleEl = card.querySelector('h3, .job-search-card__title, [class*="title"]');
                const companyEl = card.querySelector('h4, .job-search-card__company-name, [class*="company"]');
                const locationEl = card.querySelector('.job-search-card__location, [class*="location"]');
                const link = card.querySelector('a[href*="/jobs/view/"]');
                const dateEl = card.querySelector('time, [class*="date"], [class*="time"]');
                if (titleEl && link) {
                    results.push({
                        title: titleEl.innerText.trim(),
                        company: companyEl ? companyEl.innerText.trim() : '',
                        location: locationEl ? locationEl.innerText.trim() : '',
                        url: link.href.split('?')[0],  // strip tracking params
                        posted_date: dateEl ? (dateEl.getAttribute('datetime') || dateEl.innerText.trim()) : '',
                    });
                }
            });
            return results;
        }""")

        for item in cards:
            title = item.get("title", "")
            if not title or not is_pm_title(title):
                continue
            job_url = item.get("url", "")
            if job_url in seen_urls:
                continue
            seen_urls.add(job_url)

            job_id = job_url.rstrip("/").split("-")[-1]  # numeric ID at end of URL
            posted = item.get("posted_date", DATE)
            if posted and len(posted) > 10:
                posted = posted[:10]

            jobs.append({
                "id": f"linkedin-{job_id}",
                "source": "linkedin",
                "title": title,
                "company": item.get("company", "").strip(),
                "location": item.get("location", "").strip(),
                "remote": True,  # filtered by f_WT=2 (remote)
                "salary_text": "",
                "salary_min": None, "salary_max": None,
                "posted_date": posted or DATE,
                "apply_url": job_url,
                "description": "",
                "source_query": keywords,
                "scraped_at": datetime.now().isoformat(),
            })

        print(f"    '{keywords}': {len(cards)} cards → {len(jobs)} PM jobs")

    except Exception as e:
        print(f"    Error for '{keywords}': {e}")

    return jobs


async def scrape_all(max_results: int, headless: bool) -> list:
    from playwright.async_api import async_playwright

    all_jobs = []
    seen_ids = set()
    per_query = max_results // len(SEARCH_QUERIES)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        for keywords in SEARCH_QUERIES:
            jobs = await scrape_query(page, keywords, per_query)
            for j in jobs:
                if j["id"] not in seen_ids:
                    seen_ids.add(j["id"])
                    all_jobs.append(j)
            await asyncio.sleep(2)

        await browser.close()

    return all_jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=100, help="Max total jobs")
    parser.add_argument("--headless", default="true", choices=["true", "false"])
    args = parser.parse_args()

    os.makedirs("data/jobs-raw", exist_ok=True)
    headless = args.headless.lower() != "false"

    jobs = asyncio.run(scrape_all(max_results=args.max, headless=headless))

    seen = set()
    unique = [j for j in jobs if j["id"] not in seen and not seen.add(j["id"])]

    with open(OUT_FILE, "w") as f:
        json.dump(unique, f, indent=2)
    print(f"\nLinkedIn: {len(unique)} PM jobs saved to {OUT_FILE}")


if __name__ == "__main__":
    main()
