"""
Builtin.com Job Scraper
Primary: requests + JSON API (Builtin has an undocumented public API)
Fallback: Playwright
Saves to: data/jobs-raw/builtin-YYYY-MM-DD.json

Usage:
  python scripts/scrapers/scrape_builtin.py
  python scripts/scrapers/scrape_builtin.py --max 200
"""
import os, json, asyncio, argparse, time
from datetime import datetime
import requests
from dotenv import load_dotenv
load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"data/jobs-raw/builtin-{DATE}.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://builtin.com/",
}

PM_TITLES = [
    "product manager", "senior product manager", "sr. product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "head of product", "director of product",
]

def is_pm_title(title: str) -> bool:
    t = title.lower()
    return any(pm in t for pm in PM_TITLES)


def scrape_api(max_results: int = 200) -> list:
    """
    Builtin API endpoint used by their own frontend.
    GET /api/8/jobs with job_category, remote, page params.
    """
    jobs = []
    seen = set()

    # Builtin job category IDs for Product
    # category 22 = Product Management, 7 = Product
    for category_id in [22, 7]:
        page = 1
        while len(jobs) < max_results:
            try:
                resp = requests.get(
                    "https://builtin.com/api/8/jobs",
                    params={
                        "job_category": category_id,
                        "remote": 1,
                        "per_page": 50,
                        "page": page,
                    },
                    headers=HEADERS,
                    timeout=20,
                )
                if resp.status_code == 404:
                    # Try alternate endpoint
                    resp = requests.get(
                        "https://builtin.com/jobs/product-management",
                        params={"remote": "true", "page": page},
                        headers={**HEADERS, "Accept": "text/html,application/xhtml+xml"},
                        timeout=20,
                    )
                    if resp.status_code != 200:
                        break
                    # Parse HTML would be complex — just break for Playwright fallback
                    break

                if resp.status_code != 200:
                    print(f"    Builtin API page {page}: HTTP {resp.status_code}")
                    break

                data = resp.json()
                items = data if isinstance(data, list) else data.get("jobs", data.get("data", []))
                if not items:
                    break

                print(f"    Category {category_id} page {page}: {len(items)} items")

                for item in items:
                    title = item.get("title", item.get("name", ""))
                    if not title or not is_pm_title(title):
                        continue

                    job_id = str(item.get("id", item.get("slug", "")))
                    if job_id in seen:
                        continue
                    seen.add(job_id)

                    company = item.get("company", {})
                    company_name = company.get("name", "") if isinstance(company, dict) else str(company)
                    slug = item.get("slug", item.get("id", ""))
                    company_slug = company.get("slug", "") if isinstance(company, dict) else ""
                    apply_url = (item.get("url") or
                                 f"https://builtin.com/job/{company_slug}/{slug}")

                    jobs.append({
                        "id": f"builtin-{job_id}",
                        "source": "builtin",
                        "title": title.strip(),
                        "company": company_name.strip(),
                        "location": item.get("location", "Remote"),
                        "remote": item.get("remote", True),
                        "salary_text": item.get("salary", item.get("salaryRange", "")),
                        "salary_min": item.get("salaryMin"),
                        "salary_max": item.get("salaryMax"),
                        "posted_date": str(item.get("date", item.get("publishedAt", DATE)))[:10],
                        "apply_url": apply_url,
                        "description": (item.get("description", "") or "")[:2000],
                        "scraped_at": datetime.now().isoformat(),
                    })

                if len(items) < 50:
                    break
                page += 1
                time.sleep(1)

            except Exception as e:
                print(f"    Builtin API error: {e}")
                break

    return jobs


async def scrape_playwright(max_results: int = 100) -> list:
    """Playwright fallback — scrape Builtin job listing pages."""
    from playwright.async_api import async_playwright

    jobs = []
    seen = set()

    urls = [
        "https://builtin.com/jobs/product-management?remote=true",
        "https://builtin.com/jobs/product?remote=true&title=product+manager",
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )

        for url in urls:
            print(f"  Playwright → {url}")
            try:
                await page.goto(url, wait_until="networkidle", timeout=45000)
                await asyncio.sleep(3)

                for _ in range(5):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(1.5)

                job_data = await page.evaluate("""() => {
                    const results = [];
                    document.querySelectorAll('[data-id], [class*="job-card"], article').forEach(card => {
                        const titleEl = card.querySelector('h2, h3, [class*="title"], [class*="job-title"]');
                        const companyEl = card.querySelector('[class*="company"], [class*="employer"]');
                        const a = card.querySelector('a[href*="/job/"]') || card.querySelector('a');
                        if (titleEl && a) {
                            results.push({
                                title: titleEl.innerText.trim(),
                                company: companyEl ? companyEl.innerText.trim() : '',
                                url: a.href,
                                location: '',
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
                        "id": f"builtin-{job_id}",
                        "source": "builtin",
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

                    if len(jobs) >= max_results:
                        break

            except Exception as e:
                print(f"    Playwright error: {e}")

        await browser.close()
    return jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=200)
    args = parser.parse_args()

    os.makedirs("data/jobs-raw", exist_ok=True)

    print("  Trying Builtin API...")
    jobs = scrape_api(max_results=args.max)

    if not jobs:
        print("  API returned 0 — falling back to Playwright")
        jobs = asyncio.run(scrape_playwright(max_results=args.max))

    seen = set()
    unique = [j for j in jobs if j["id"] not in seen and not seen.add(j["id"])]

    with open(OUT_FILE, "w") as f:
        json.dump(unique, f, indent=2)
    print(f"\nBuiltin: {len(unique)} PM jobs saved to {OUT_FILE}")


if __name__ == "__main__":
    main()
