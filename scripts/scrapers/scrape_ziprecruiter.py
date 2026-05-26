"""
ZipRecruiter Job Scraper
Method: Playwright (JS-rendered, blocks plain requests)
Saves to: data/jobs-raw/ziprecruiter-YYYY-MM-DD.json

Usage:
  python scripts/scrapers/scrape_ziprecruiter.py
  python scripts/scrapers/scrape_ziprecruiter.py --max 100
"""
import os, json, asyncio, re, argparse
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = Path(f"data/jobs-raw/ziprecruiter-{DATE}.json")

PM_TITLES = [
    "product manager", "senior product manager", "sr. product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "group product manager", "head of product",
]
EXCLUDE_TITLES = ["marketing", "sales", "recruiter", "data scientist", "engineer", "developer",
                  "designer", "analyst", "director", "vp", "vice president", "chief"]

SEARCH_QUERIES = [
    ("product manager", "Remote"),
    ("senior product manager", "Remote"),
    ("AI product manager", "Remote"),
    ("platform product manager", "Remote"),
]

def is_pm_title(title: str) -> bool:
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_TITLES):
        return False
    return any(pm in t for pm in PM_TITLES)

def parse_salary(text: str):
    if not text:
        return None, None
    text = text.replace("K", "000").replace("k", "000")
    nums = re.findall(r"[\d,]+", text)
    nums = [int(n.replace(",", "")) for n in nums if int(n.replace(",", "")) > 10000]
    if len(nums) >= 2:
        return min(nums), max(nums)
    elif len(nums) == 1:
        return nums[0], nums[0]
    return None, None

def parse_posted_date(text: str) -> str:
    """Convert '2 days ago', '1 week ago' → YYYY-MM-DD."""
    text = (text or "").lower().strip()
    today = datetime.now().date()
    if "today" in text or "just" in text or "hour" in text:
        return str(today)
    m = re.search(r"(\d+)\s*day", text)
    if m:
        return str(today - timedelta(days=int(m.group(1))))
    m = re.search(r"(\d+)\s*week", text)
    if m:
        return str(today - timedelta(weeks=int(m.group(1))))
    m = re.search(r"(\d+)\s*month", text)
    if m:
        return str(today - timedelta(days=int(m.group(1)) * 30))
    return str(today)

async def scrape_query(page, query: str, location: str, max_jobs: int) -> list:
    jobs = []
    seen_urls = set()
    url = f"https://www.ziprecruiter.com/candidate/search?search={query.replace(' ', '+')}&location={location.replace(' ', '+')}&days=7"

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        await asyncio.sleep(3)

        # Scroll to load more
        for _ in range(min(5, max_jobs // 20)):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)

        # Extract job cards
        cards = await page.evaluate("""() => {
            const jobs = [];
            const cards = document.querySelectorAll(
                '[data-testid="job-card"], .job_content, article[class*="job"], [class*="jobCard"], [class*="job-card"]'
            );
            cards.forEach(card => {
                const titleEl = card.querySelector('h2 a, h3 a, [class*="title"] a, a[class*="title"]');
                const companyEl = card.querySelector('[class*="company"], [data-testid="company-name"]');
                const locationEl = card.querySelector('[class*="location"], [data-testid="job-location"]');
                const salaryEl = card.querySelector('[class*="salary"], [data-testid="salary"]');
                const dateEl = card.querySelector('[class*="date"], [class*="age"], time');
                const descEl = card.querySelector('[class*="snippet"], [class*="description"], p');

                if (titleEl) {
                    jobs.push({
                        title: titleEl.innerText.trim(),
                        url: titleEl.href || '',
                        company: companyEl ? companyEl.innerText.trim() : '',
                        location: locationEl ? locationEl.innerText.trim() : '',
                        salary: salaryEl ? salaryEl.innerText.trim() : '',
                        posted: dateEl ? dateEl.innerText.trim() : '',
                        snippet: descEl ? descEl.innerText.trim() : '',
                    });
                }
            });
            return jobs;
        }""")

        for c in cards:
            title = c.get("title", "")
            if not title or not is_pm_title(title):
                continue
            job_url = c.get("url", "")
            if not job_url or job_url in seen_urls:
                continue
            seen_urls.add(job_url)

            salary_text = c.get("salary", "")
            salary_min, salary_max = parse_salary(salary_text)
            location = c.get("location", "")
            remote = "remote" in location.lower() or "remote" in query.lower()

            jobs.append({
                "id": f"ziprecruiter-{hash(job_url) % 10**10}",
                "source": "ziprecruiter",
                "title": title,
                "company": c.get("company", "").strip(),
                "location": location.strip(),
                "remote": remote,
                "salary_text": salary_text.strip(),
                "salary_min": salary_min,
                "salary_max": salary_max,
                "posted_date": parse_posted_date(c.get("posted", "")),
                "apply_url": job_url,
                "description": c.get("snippet", ""),
                "source_query": query,
                "scraped_at": datetime.now().isoformat(),
            })

        print(f"    '{query}': {len(cards)} cards → {len(jobs)} PM jobs")
    except Exception as e:
        print(f"    Error for '{query}': {e}")

    return jobs


async def scrape_all(max_results: int) -> list:
    from playwright.async_api import async_playwright
    all_jobs = []
    seen_ids = set()
    per_query = max_results // len(SEARCH_QUERIES)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()

        for query, location in SEARCH_QUERIES:
            jobs = await scrape_query(page, query, location, per_query)
            for j in jobs:
                if j["id"] not in seen_ids:
                    seen_ids.add(j["id"])
                    all_jobs.append(j)
            await asyncio.sleep(2)

        await browser.close()

    return all_jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=100)
    args = parser.parse_args()

    Path("data/jobs-raw").mkdir(parents=True, exist_ok=True)
    print("ZipRecruiter scraper — Playwright")
    jobs = asyncio.run(scrape_all(args.max))

    seen, final = set(), []
    for j in jobs:
        if j["id"] not in seen:
            seen.add(j["id"])
            final.append(j)

    OUT_FILE.write_text(json.dumps(final, indent=2))
    salary_count = sum(1 for j in final if j.get("salary_text"))
    print(f"\nZipRecruiter: {len(final)} PM jobs saved to {OUT_FILE}")
    print(f"  With salary: {salary_count}")


if __name__ == "__main__":
    main()
