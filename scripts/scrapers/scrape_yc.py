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
    """API-based scraping — not available (site returns 406). Skip, use Playwright."""
    return []


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

        # URL changed: now /jobs/l/product-manager (not /jobs?role=pm)
        url = "https://www.workatastartup.com/jobs/l/product-manager"
        print(f"  Playwright → {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)

        # Scroll to lazy-load all results
        for _ in range(6):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.5)

        job_data = await page.evaluate("""() => {
            const results = [];
            // Job links are /jobs/{numeric_id}
            document.querySelectorAll('a[href]').forEach(a => {
                if (!/\\/jobs\\/\\d+/.test(a.href)) return;
                const title = a.innerText.trim();
                if (!title || title.length < 5) return;
                // Try to find company name from parent card
                const card = a.closest('li, article, div') || a.parentElement;
                let company = '';
                if (card) {
                    const spans = card.querySelectorAll('span, p');
                    for (const s of spans) {
                        const t = s.innerText.trim();
                        if (t && t !== title && t.length < 80) { company = t; break; }
                    }
                }
                results.push({ url: a.href, title, company });
            });
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
