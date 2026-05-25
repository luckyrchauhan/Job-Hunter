"""
Niche Job Boards Scraper
Sources:
  - ProductHunt Jobs (https://www.producthunt.com/jobs)
  - Pragmatic Engineer Job Board (https://pragmatic-engineer.pallet.com/jobs)
  - Lenny's Job Board (https://lennys-jobs.pallet.com/jobs)
  - NFX Jobs (https://jobs.nfx.com/)
  - Pallet boards (multiple PM-focused boards)

Saves to: data/jobs-raw/niche-YYYY-MM-DD.json

Usage:
  python scripts/scrapers/scrape_niche.py
"""
import os, json, asyncio
from datetime import datetime
import requests
from dotenv import load_dotenv
load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"data/jobs-raw/niche-{DATE}.json"

HEADERS = {"User-Agent": "JobHunter/1.0 (your.email@example.com)", "Accept": "application/json"}

PM_TITLES = [
    "product manager", "senior product manager", "sr. product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "head of product", "director of product",
]

PALLET_BOARDS = [
    {"name": "Lenny's Jobs", "slug": "lennys-jobs"},
    {"name": "Pragmatic Engineer", "slug": "pragmatic-engineer"},
    {"name": "The Product Compass", "slug": "the-product-compass"},
    {"name": "NFX Jobs", "slug": "nfx"},
]

def is_pm_title(title: str) -> bool:
    t = title.lower()
    return any(pm in t for pm in PM_TITLES)


def scrape_pallet_board(name: str, slug: str) -> list:
    """Pallet boards have a public JSON API."""
    jobs = []
    try:
        resp = requests.get(
            f"https://{slug}.pallet.com/api/v1/jobs",
            params={"limit": 100, "page": 1},
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code == 404:
            # Try alternate URL pattern
            resp = requests.get(
                f"https://pallet.com/list/{slug}/jobs",
                params={"limit": 100},
                headers=HEADERS,
                timeout=15,
            )

        if resp.status_code != 200:
            return []

        data = resp.json()
        items = data if isinstance(data, list) else data.get("jobs", data.get("data", data.get("results", [])))

        for item in items:
            title = item.get("title", item.get("name", item.get("role", "")))
            if not title or not is_pm_title(title):
                continue

            company = item.get("company", item.get("companyName", item.get("organization", {})))
            if isinstance(company, dict):
                company = company.get("name", company.get("display_name", ""))

            job_id = str(item.get("id", item.get("slug", "")[:60]))
            jobs.append({
                "id": f"niche-{slug}-{job_id}",
                "source": f"niche_{slug.replace('-', '_')}",
                "title": title.strip(),
                "company": company.strip() if isinstance(company, str) else "",
                "location": item.get("location", "Remote"),
                "remote": item.get("remote", True),
                "salary_text": item.get("salary", item.get("compensation", "")),
                "salary_min": None, "salary_max": None,
                "posted_date": str(item.get("publishedAt", item.get("created_at", DATE)))[:10],
                "apply_url": item.get("url", item.get("applyUrl", f"https://{slug}.pallet.com/jobs/{job_id}")),
                "description": (item.get("description", item.get("body", "")) or "")[:2000],
                "scraped_at": datetime.now().isoformat(),
            })

        print(f"  {name}: {len(jobs)} PM jobs")
    except Exception as e:
        print(f"  {name} error: {e}")
    return jobs


async def scrape_producthunt() -> list:
    """ProductHunt Jobs — scrape via Playwright since it's React."""
    from playwright.async_api import async_playwright

    jobs = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            await page.goto("https://www.producthunt.com/jobs?category=product", wait_until="networkidle", timeout=45000)
            await asyncio.sleep(3)

            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.5)

            job_data = await page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('[class*="job"], [data-test*="job"], article').forEach(card => {
                    const titleEl = card.querySelector('h2, h3, [class*="title"]');
                    const companyEl = card.querySelector('[class*="company"], [class*="maker"]');
                    const a = card.querySelector('a[href*="/jobs/"]') || card.querySelector('a');
                    if (titleEl && a) {
                        results.push({
                            title: titleEl.innerText.trim(),
                            company: companyEl ? companyEl.innerText.trim() : '',
                            url: a.href,
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
                job_id = job_url.rstrip("/").split("/")[-1]
                jobs.append({
                    "id": f"niche-ph-{job_id}",
                    "source": "niche_producthunt",
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

            await browser.close()
        print(f"  ProductHunt: {len(jobs)} PM jobs")
    except Exception as e:
        print(f"  ProductHunt error: {e}")
    return jobs


def main():
    os.makedirs("data/jobs-raw", exist_ok=True)

    all_jobs = []
    seen = set()

    # Pallet boards (JSON API)
    for board in PALLET_BOARDS:
        jobs = scrape_pallet_board(board["name"], board["slug"])
        for j in jobs:
            if j["id"] not in seen:
                seen.add(j["id"])
                all_jobs.append(j)

    # ProductHunt (Playwright)
    ph_jobs = asyncio.run(scrape_producthunt())
    for j in ph_jobs:
        if j["id"] not in seen:
            seen.add(j["id"])
            all_jobs.append(j)

    with open(OUT_FILE, "w") as f:
        json.dump(all_jobs, f, indent=2)
    print(f"\nNiche Boards: {len(all_jobs)} PM jobs saved to {OUT_FILE}")


if __name__ == "__main__":
    main()
