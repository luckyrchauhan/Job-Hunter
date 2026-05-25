"""
Wellfound (AngelList) Job Scraper
Primary: Apify actor antoine_vdb/wellfound-scraper or mscraper/wellfound-jobs-scraper
Fallback: Playwright (Wellfound requires login for apply — scrape listing page only)
Saves to: data/jobs-raw/wellfound-YYYY-MM-DD.json

Usage:
  python scripts/scrapers/scrape_wellfound.py
  python scripts/scrapers/scrape_wellfound.py --playwright

Requires: APIFY_API_TOKEN in .env for Apify mode
"""
import os, json, time, asyncio, argparse
from datetime import datetime
import requests
from dotenv import load_dotenv
load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"data/jobs-raw/wellfound-{DATE}.json"
APIFY_TOKEN = os.getenv("APIFY_API_TOKEN", "")

PM_TITLES = [
    "product manager", "senior product manager", "sr. product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "head of product", "director of product",
]

SEARCH_URLS = [
    "https://wellfound.com/role/r/product-manager?remote=true",
    "https://wellfound.com/role/r/senior-product-manager?remote=true",
]

def is_pm_title(title: str) -> bool:
    t = title.lower()
    return any(pm in t for pm in PM_TITLES)


def run_actor(actor_id: str, payload: dict, timeout: int = 180) -> list:
    base_url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
    try:
        resp = requests.post(
            base_url,
            params={"token": APIFY_TOKEN, "timeout": timeout, "memory": 1024},
            json=payload, timeout=timeout + 30,
        )
        if resp.status_code not in (200, 201):
            print(f"    HTTP {resp.status_code}: {resp.text[:200]}")
            return []
        data = resp.json()
        return data if isinstance(data, list) else data.get("items", [])
    except Exception as e:
        print(f"    Actor error: {e}")
        return []


def scrape_apify() -> list:
    if not APIFY_TOKEN:
        return []

    all_jobs = []
    seen = set()

    # Try multiple known Wellfound actors
    actors = [
        ("mscraper~wellfound-jobs-scraper", {
            "role": "product-manager",
            "remote": True,
            "maxItems": 100,
        }),
        ("antoine_vdb~wellfound-scraper", {
            "startUrls": [{"url": u} for u in SEARCH_URLS],
            "maxItems": 100,
        }),
    ]

    for actor_id, payload in actors:
        print(f"  Wellfound actor: {actor_id}")
        items = run_actor(actor_id, payload, timeout=180)
        print(f"    → {len(items)} items")
        if not items:
            continue

        for item in items:
            title = item.get("title", item.get("jobTitle", item.get("role", "")))
            if not title or not is_pm_title(title):
                continue

            job_id = str(item.get("id", item.get("url", "")[:80]))
            if job_id in seen:
                continue
            seen.add(job_id)

            company = item.get("company", item.get("companyName", item.get("startupName", "")))
            if isinstance(company, dict):
                company = company.get("name", "")

            all_jobs.append({
                "id": f"wellfound-{job_id}",
                "source": "wellfound",
                "title": title.strip(),
                "company": company.strip() if isinstance(company, str) else "",
                "location": item.get("location", "Remote"),
                "remote": item.get("remote", True),
                "salary_text": item.get("compensation", item.get("salary", "")),
                "salary_min": None, "salary_max": None,
                "posted_date": str(item.get("postedAt", item.get("createdAt", DATE)))[:10],
                "apply_url": item.get("url", item.get("applyUrl", "")),
                "description": (item.get("description", item.get("jobDescription", "")) or "")[:2000],
                "scraped_at": datetime.now().isoformat(),
            })

        if all_jobs:
            break  # First working actor is enough
        time.sleep(3)

    return all_jobs


async def scrape_playwright() -> list:
    """Playwright fallback — scrapes Wellfound public listing pages."""
    from playwright.async_api import async_playwright

    jobs = []
    seen = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )

        for url in SEARCH_URLS:
            print(f"  Playwright → {url}")
            try:
                await page.goto(url, wait_until="networkidle", timeout=45000)
                await asyncio.sleep(3)

                for _ in range(5):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(1.5)

                job_data = await page.evaluate("""() => {
                    const results = [];
                    document.querySelectorAll('[class*="job"], [class*="listing"], [data-test*="job"]').forEach(card => {
                        const a = card.querySelector('a[href*="/jobs/"]');
                        const titleEl = card.querySelector('h2, h3, [class*="title"]');
                        const companyEl = card.querySelector('[class*="company"], [class*="startup"]');
                        if (a && titleEl) {
                            results.push({
                                url: a.href,
                                title: titleEl.innerText.trim(),
                                company: companyEl ? companyEl.innerText.trim() : '',
                            });
                        }
                    });
                    return results;
                }""")

                for j in job_data:
                    title = j.get("title", "")
                    if not title or not is_pm_title(title):
                        continue
                    job_url = j.get("url", "")
                    if job_url in seen:
                        continue
                    seen.add(job_url)
                    job_id = job_url.rstrip("/").split("/")[-1]
                    jobs.append({
                        "id": f"wellfound-{job_id}",
                        "source": "wellfound",
                        "title": title,
                        "company": j.get("company", ""),
                        "location": "Remote",
                        "remote": True,
                        "salary_text": "",
                        "salary_min": None, "salary_max": None,
                        "posted_date": DATE,
                        "apply_url": job_url,
                        "description": "",
                        "scraped_at": datetime.now().isoformat(),
                    })
            except Exception as e:
                print(f"    Playwright error: {e}")

        await browser.close()
    return jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--playwright", action="store_true")
    args = parser.parse_args()

    os.makedirs("data/jobs-raw", exist_ok=True)

    jobs = []
    if not args.playwright and APIFY_TOKEN:
        print("  Using Apify...")
        jobs = scrape_apify()

    if not jobs:
        print("  Falling back to Playwright...")
        jobs = asyncio.run(scrape_playwright())

    seen = set()
    unique = [j for j in jobs if j["id"] not in seen and not seen.add(j["id"])]

    with open(OUT_FILE, "w") as f:
        json.dump(unique, f, indent=2)
    print(f"\nWellfound: {len(unique)} PM jobs saved to {OUT_FILE}")


if __name__ == "__main__":
    main()
