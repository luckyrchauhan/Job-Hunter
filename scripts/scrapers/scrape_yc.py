"""
YC Work at a Startup Scraper
Primary: JSON API endpoint (fast, structured)
Fallback: Playwright with fixed selectors
Saves to: data/jobs-raw/yc-YYYY-MM-DD.json

Usage:
  python scripts/scrapers/scrape_yc.py
  python scripts/scrapers/scrape_yc.py --headless false   # debug UI
  python scripts/scrapers/scrape_yc.py --playwright       # force Playwright
"""
import os, json, asyncio, argparse, time
from datetime import datetime
import requests
from dotenv import load_dotenv
load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"data/jobs-raw/yc-{DATE}.json"

PM_TITLE_TOKENS = [
    "product manager", "product management", "head of product", "director of product",
    "vp of product", "vp product", "group product manager", "staff product manager",
    "principal product manager", "associate product manager", "apm"
]

def is_pm_title(title: str) -> bool:
    t = title.lower()
    return any(tok in t for tok in PM_TITLE_TOKENS)


# ─── Primary: JSON API ─────────────────────────────────────────────────────────

def scrape_api() -> list:
    """
    Work at a Startup exposes a public API used by their own frontend.
    Endpoint: GET /api/jobs  params: role=pm, visa=true, remote=true
    Returns paginated JSON with full job objects.
    """
    jobs = []
    seen = set()
    headers = {"User-Agent": "JobHunter/1.0 (lucky.raajc@gmail.com)",
               "Accept": "application/json"}

    # Try multiple known API paths
    endpoints = [
        "https://www.workatastartup.com/api/jobs",
        "https://api.workatastartup.com/v2/jobs",
    ]
    params = {"role": "pm", "visa": "true", "remote": "true", "limit": 100, "page": 1}

    for base_url in endpoints:
        try:
            resp = requests.get(base_url, params=params, headers=headers, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                raw_jobs = data if isinstance(data, list) else data.get("jobs", data.get("results", []))
                print(f"  API {base_url}: {len(raw_jobs)} raw jobs")
                for j in raw_jobs:
                    job_id = str(j.get("id", j.get("slug", "")))
                    title = j.get("title", j.get("name", ""))
                    if not title or job_id in seen:
                        continue
                    if not is_pm_title(title):
                        continue
                    seen.add(job_id)
                    company = j.get("company", {})
                    company_name = company.get("name", "") if isinstance(company, dict) else str(company)
                    jobs.append({
                        "id": f"yc-{job_id}",
                        "source": "yc_jobs",
                        "title": title.strip(),
                        "company": company_name,
                        "location": j.get("location", "Remote"),
                        "remote": j.get("remote", True),
                        "visa_sponsored": True,  # filtered by visa=true param
                        "salary_min": j.get("salaryMin") or j.get("salary_min"),
                        "salary_max": j.get("salaryMax") or j.get("salary_max"),
                        "posted_date": j.get("createdAt", j.get("created_at", DATE))[:10],
                        "apply_url": j.get("url") or f"https://www.workatastartup.com/jobs/{job_id}",
                        "description": (j.get("description") or j.get("body") or "")[:2000],
                        "scraped_at": datetime.now().isoformat(),
                    })
                if jobs:
                    return jobs
        except Exception as e:
            print(f"  API {base_url} error: {e}")
            continue
    return jobs


# ─── Fallback: Playwright ──────────────────────────────────────────────────────

async def scrape_playwright(headless: bool = True) -> list:
    """Playwright fallback — scrapes /jobs?role=pm&visa=true directly."""
    from playwright.async_api import async_playwright

    jobs = []
    seen = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )

        url = "https://www.workatastartup.com/jobs?role=pm&visa=true&remote=true"
        print(f"  Playwright → {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(4)

        # Scroll to lazy-load all results
        for _ in range(6):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.5)

        # Work at a Startup job card selectors (as of 2025)
        job_data = await page.evaluate("""() => {
            const results = [];
            // Try multiple selector strategies
            const selectors = [
                '.job-name',
                '[data-page-load-event="Job Viewed"]',
                'div[class*="job"] a[href*="/jobs/"]',
                'a[href*="/jobs/"][class*="title"]',
            ];

            // Strategy 1: data attribute cards
            document.querySelectorAll('[data-job-id]').forEach(card => {
                const a = card.querySelector('a[href*="/jobs/"]');
                const titleEl = card.querySelector('[class*="title"], h2, h3, strong');
                const companyEl = card.querySelector('[class*="company"], [class*="name"]');
                if (a) results.push({
                    url: a.href,
                    title: titleEl ? titleEl.innerText.trim() : (a.innerText.trim()),
                    company: companyEl ? companyEl.innerText.trim() : '',
                    card_text: card.innerText.substring(0, 400),
                });
            });

            // Strategy 2: fallback — all links to /jobs/
            if (results.length === 0) {
                document.querySelectorAll('a[href*="/jobs/"]').forEach(a => {
                    if (a.href.match(/\\/jobs\\/\\d+/)) {
                        const parent = a.closest('li, article, div[class*="job"], div[class*="listing"]') || a.parentElement;
                        results.push({
                            url: a.href,
                            title: a.innerText.trim() || a.title || '',
                            company: '',
                            card_text: parent ? parent.innerText.substring(0, 400) : '',
                        });
                    }
                });
            }
            return results;
        }""")

        print(f"  Playwright found {len(job_data)} raw links")

        for j in job_data:
            url = j.get("url", "")
            title = j.get("title", "").strip()
            if not url or not title or url in seen:
                continue
            if not is_pm_title(title):
                continue
            seen.add(url)
            job_id = url.rstrip("/").split("/")[-1]
            jobs.append({
                "id": f"yc-{job_id}",
                "source": "yc_jobs",
                "title": title,
                "company": j.get("company", "").strip(),
                "location": "Remote",
                "remote": True,
                "visa_sponsored": True,
                "salary_min": None,
                "salary_max": None,
                "posted_date": DATE,
                "apply_url": url,
                "description": j.get("card_text", ""),
                "scraped_at": datetime.now().isoformat(),
            })

        await browser.close()

    return jobs


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", default="true", choices=["true", "false"])
    parser.add_argument("--playwright", action="store_true", help="Force Playwright (skip API)")
    args = parser.parse_args()

    os.makedirs("data/jobs-raw", exist_ok=True)
    headless = args.headless.lower() != "false"

    jobs = []
    if not args.playwright:
        print("  Trying JSON API...")
        jobs = scrape_api()

    if not jobs:
        print("  API returned 0 jobs — falling back to Playwright")
        jobs = asyncio.run(scrape_playwright(headless=headless))

    with open(OUT_FILE, "w") as f:
        json.dump(jobs, f, indent=2)
    print(f"YC Jobs: {len(jobs)} PM jobs saved to {OUT_FILE}")


if __name__ == "__main__":
    main()
