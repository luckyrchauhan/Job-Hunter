"""
AI Jobs Scraper (aijobs.net + otta.com + thesequoia.io)
Method: Playwright for JS-rendered boards, requests for APIs
Saves to: data/jobs-raw/aijobs-YYYY-MM-DD.json

Sources:
  - aijobs.net       — AI-specific job board
  - otta.com         — curated tech jobs, good PM listings
  - workatastartup.com (YC) — already covered by scrape_yc.py

Usage:
  python scripts/scrapers/scrape_aijobs.py
"""
import json, re, asyncio, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = Path(f"data/jobs-raw/aijobs-{DATE}.json")

PM_TITLES = [
    "product manager", "senior product manager", "sr. product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "group product manager", "head of product",
]
EXCLUDE_TITLES = [
    "marketing", "sales", "recruiter", "software engineer", "developer",
    "designer", "data scientist", "director", "vp", "vice president",
]

def is_pm_title(title: str) -> bool:
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_TITLES):
        return False
    return any(pm in t for pm in PM_TITLES)

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


async def scrape_aijobs_net(page) -> list:
    """Scrape aijobs.net — AI/ML specific job board."""
    jobs = []
    seen = set()
    queries = ["product-manager", "ai-product-manager"]

    for query in queries:
        try:
            url = f"https://aijobs.net/jobs/?q={query}&remote=true"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)

            cards = await page.evaluate("""() => {
                const jobs = [];
                document.querySelectorAll('article, [class*="job"], [class*="listing"]').forEach(c => {
                    const t = c.querySelector('h2, h3, [class*="title"]');
                    const co = c.querySelector('[class*="company"]');
                    const loc = c.querySelector('[class*="location"]');
                    const sal = c.querySelector('[class*="salary"], [class*="comp"]');
                    const a = c.querySelector('a[href*="/job"], a[href*="/jobs"]');
                    const dt = c.querySelector('time, [class*="date"]');
                    if (t) jobs.push({
                        title: t.innerText.trim(),
                        company: co ? co.innerText.trim() : '',
                        location: loc ? loc.innerText.trim() : '',
                        salary: sal ? sal.innerText.trim() : '',
                        url: a ? (a.href.startsWith('http') ? a.href : 'https://aijobs.net' + a.getAttribute('href')) : '',
                        posted: dt ? dt.innerText.trim() : '',
                    });
                });
                return jobs;
            }""")

            for c in cards:
                t = c.get("title", "")
                if not t or not is_pm_title(t):
                    continue
                u = c.get("url", "")
                if not u or u in seen:
                    continue
                seen.add(u)
                sal = c.get("salary", "")
                s_min, s_max = parse_salary(sal)
                loc = c.get("location", "")
                jobs.append({
                    "id": f"aijobs-{hash(u) % 10**10}",
                    "source": "aijobs",
                    "title": t,
                    "company": c.get("company", "").strip(),
                    "location": loc.strip(),
                    "remote": "remote" in loc.lower(),
                    "salary_text": sal.strip(),
                    "salary_min": s_min,
                    "salary_max": s_max,
                    "posted_date": parse_posted(c.get("posted", "")),
                    "apply_url": u,
                    "description": "",
                    "source_query": query,
                    "scraped_at": datetime.now().isoformat(),
                })
            print(f"  aijobs.net '{query}': {len(cards)} cards → {len([j for j in jobs if j['source_query']==query])} PM jobs")
        except Exception as e:
            print(f"  aijobs.net error '{query}': {e}")

    return jobs


async def scrape_otta(page) -> list:
    """Scrape otta.com — curated tech jobs with good PM listings."""
    jobs = []
    seen = set()

    try:
        url = "https://app.otta.com/jobs/search?role=product-management&remote=true"
        await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        await asyncio.sleep(5)  # Otta needs longer to render

        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)

        cards = await page.evaluate("""() => {
            const jobs = [];
            document.querySelectorAll('[class*="JobCard"], [data-testid*="job"], [class*="job-card"]').forEach(c => {
                const t = c.querySelector('h2, h3, [class*="title"]');
                const co = c.querySelector('[class*="company"], [class*="Company"]');
                const loc = c.querySelector('[class*="location"], [class*="Location"]');
                const sal = c.querySelector('[class*="salary"], [class*="Salary"]');
                const a = c.querySelector('a');
                if (t && a) jobs.push({
                    title: t.innerText.trim(),
                    company: co ? co.innerText.trim() : '',
                    location: loc ? loc.innerText.trim() : '',
                    salary: sal ? sal.innerText.trim() : '',
                    url: a.href || '',
                });
            });
            return jobs;
        }""")

        for c in cards:
            t = c.get("title", "")
            if not t or not is_pm_title(t):
                continue
            u = c.get("url", "")
            if not u or u in seen:
                continue
            seen.add(u)
            sal = c.get("salary", "")
            s_min, s_max = parse_salary(sal)
            loc = c.get("location", "")
            jobs.append({
                "id": f"otta-{hash(u) % 10**10}",
                "source": "otta",
                "title": t,
                "company": c.get("company", "").strip(),
                "location": loc.strip(),
                "remote": "remote" in loc.lower(),
                "salary_text": sal.strip(),
                "salary_min": s_min,
                "salary_max": s_max,
                "posted_date": DATE,
                "apply_url": u,
                "description": "",
                "source_query": "product-management",
                "scraped_at": datetime.now().isoformat(),
            })

        print(f"  otta.com: {len(cards)} cards → {len(jobs)} PM jobs")
    except Exception as e:
        print(f"  otta.com error: {e}")

    return jobs


async def scrape_all() -> list:
    from playwright.async_api import async_playwright
    all_jobs = []
    seen_ids = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()

        # AI Jobs
        jobs = await scrape_aijobs_net(page)
        for j in jobs:
            if j["id"] not in seen_ids:
                seen_ids.add(j["id"])
                all_jobs.append(j)

        # Otta
        jobs = await scrape_otta(page)
        for j in jobs:
            if j["id"] not in seen_ids:
                seen_ids.add(j["id"])
                all_jobs.append(j)

        await browser.close()

    return all_jobs


def main():
    Path("data/jobs-raw").mkdir(parents=True, exist_ok=True)
    print("AI Jobs + Otta scraper — Playwright")
    jobs = asyncio.run(scrape_all())

    OUT_FILE.write_text(json.dumps(jobs, indent=2))
    salary_count = sum(1 for j in jobs if j.get("salary_text"))
    print(f"\nAI Jobs+Otta: {len(jobs)} PM jobs saved to {OUT_FILE}")
    print(f"  With salary: {salary_count}")


if __name__ == "__main__":
    main()
