"""
LinkedIn Job Scraper
Method: Apify actor `hKByXkMQaC5Qt9UMN` (linkedin-jobs-scraper) — returns full JD + salary
Fallback: Playwright public search (cards only, no description)
Saves to: data/jobs-raw/linkedin-YYYY-MM-DD.json

Usage:
  python scripts/scrapers/scrape_linkedin.py
  python scripts/scrapers/scrape_linkedin.py --max 200
"""
import os, json, time, re, argparse, urllib.request, urllib.parse, urllib.error
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATE = datetime.now().strftime("%Y-%m-%d")
OUT_FILE = f"data/jobs-raw/linkedin-{DATE}.json"
APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
ACTOR_ID = "RIGGeqD6RqKmlVoQU"  # 🏆 LinkedIn Jobs Scraper (URL-based input, 145k runs)

SEARCH_QUERIES = [
    "product manager",
    "senior product manager",
    "AI product manager",
    "platform product manager",
]

PM_TITLES = [
    "product manager", "senior product manager", "sr. product manager",
    "associate product manager", "apm", "ai product manager",
    "platform product manager", "technical product manager",
    "staff product manager", "principal product manager",
    "head of product", "director of product", "vp of product",
    "group product manager",
]

def is_pm_title(title: str) -> bool:
    t = title.lower()
    return any(pm in t for pm in PM_TITLES)


def parse_salary(text: str):
    """Extract salary_min, salary_max from salary string like '$130K-$160K/yr'."""
    if not text:
        return None, None
    nums = re.findall(r"[\d,]+", text.replace("K", "000").replace("k", "000"))
    nums = [int(n.replace(",", "")) for n in nums if int(n.replace(",", "")) > 1000]
    if len(nums) >= 2:
        return min(nums), max(nums)
    elif len(nums) == 1:
        return nums[0], nums[0]
    return None, None


LINKEDIN_SEARCH_URLS = [
    # Remote PM jobs, past week
    "https://www.linkedin.com/jobs/search/?keywords=product+manager&location=United+States&f_WT=2&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=senior+product+manager&location=United+States&f_WT=2&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=AI+product+manager&location=United+States&f_WT=2&f_TPR=r604800",
    "https://www.linkedin.com/jobs/search/?keywords=platform+product+manager&location=United+States&f_WT=2&f_TPR=r604800",
]


def apify_run(query: str, max_items: int) -> list:
    """Run Apify LinkedIn actor for one query, return raw items."""
    # Actor RIGGeqD6RqKmlVoQU uses URL-based input
    search_url = f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(query)}&location=United+States&f_WT=2&f_TPR=r604800"
    payload = json.dumps({
        "urls": [search_url],
        "maxItems": max_items,
    }).encode()

    # Start run
    start_url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs?token={APIFY_TOKEN}"
    req = urllib.request.Request(start_url, data=payload,
                                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            run_data = json.loads(r.read())
    except Exception as e:
        print(f"    Apify start error for '{query}': {e}")
        return []

    run_id = run_data.get("data", {}).get("id", "")
    if not run_id:
        print(f"    No run ID returned for '{query}'")
        return []

    # Poll until finished
    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
    for attempt in range(50):  # max ~5 min wait
        time.sleep(6)
        try:
            with urllib.request.urlopen(status_url, timeout=15) as r:
                status_data = json.loads(r.read())
            status = status_data.get("data", {}).get("status", "")
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
        except Exception:
            continue
    else:
        print(f"    Timeout waiting for Apify run '{query}'")
        return []

    if status != "SUCCEEDED":
        print(f"    Apify run {status} for '{query}'")
        return []

    # Fetch dataset
    dataset_id = status_data["data"].get("defaultDatasetId", "")
    items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}&clean=true&limit={max_items}"
    try:
        with urllib.request.urlopen(items_url, timeout=30) as r:
            items = json.loads(r.read())
        return items
    except Exception as e:
        print(f"    Dataset fetch error for '{query}': {e}")
        return []


def normalize_item(item: dict, query: str) -> dict:
    """Map Apify RIGGeqD6RqKmlVoQU actor fields → standard job schema."""
    # Field names from this actor: id, url, title, location, postedDate,
    # companyName, salary, workType, description, applyUrl
    title = item.get("title", "") or ""
    company = item.get("companyName", "") or item.get("company", "") or ""
    location = item.get("location", "") or ""
    url = item.get("url", "") or item.get("applyUrl", "") or ""
    description = item.get("description", "") or item.get("descriptionHtml", "") or ""
    salary_text = item.get("salary", "") or ""
    posted_raw = item.get("postedDate", "") or ""

    # Parse posted date
    try:
        posted = datetime.fromisoformat(posted_raw[:10]).strftime("%Y-%m-%d")
    except Exception:
        posted = DATE

    # Parse salary
    salary_min, salary_max = parse_salary(salary_text)

    # Remote detection — workType field from this actor is actually sector, not work type
    # Use contractType and location instead
    work_type = item.get("contractType", "").lower()
    remote = (
        "remote" in location.lower() or
        "remote" in work_type or
        "remote" in (description or "").lower()[:300]
    )

    # Job ID
    job_id = str(item.get("id", "")) or url.rstrip("/").split("-")[-1]

    return {
        "id": f"linkedin-{job_id}",
        "source": "linkedin",
        "title": title.strip(),
        "company": company.strip(),
        "location": location.strip(),
        "remote": remote,
        "salary_text": salary_text.strip(),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "posted_date": posted,
        "apply_url": url,
        "description": description,
        "applicant_count": item.get("applicationsCount", ""),
        "source_query": query,
        "scraped_at": datetime.now().isoformat(),
    }


def scrape_apify(max_results: int) -> list:
    all_jobs = []
    seen_ids = set()
    per_query = max(20, max_results // len(SEARCH_QUERIES))

    for query in SEARCH_QUERIES:
        print(f"  Apify LinkedIn — '{query}' (max {per_query})")
        items = apify_run(query, per_query)
        count = 0
        for item in items:
            norm = normalize_item(item, query)
            if not is_pm_title(norm["title"]):
                continue
            if norm["id"] in seen_ids:
                continue
            seen_ids.add(norm["id"])
            all_jobs.append(norm)
            count += 1
        desc_count = sum(1 for j in all_jobs if j.get("description"))
        print(f"    → {count} PM jobs ({desc_count} with full description)")

    return all_jobs


def scrape_playwright_fallback(max_results: int) -> list:
    """Fallback: Playwright card scrape (no descriptions)."""
    import asyncio

    async def _scrape():
        from playwright.async_api import async_playwright
        jobs = []
        seen = set()
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await (await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )).new_page()

            for query in SEARCH_QUERIES:
                url = (f"https://www.linkedin.com/jobs/search/"
                       f"?keywords={urllib.parse.quote(query)}"
                       f"&location=United+States&f_WT=2&f_TPR=r604800")
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(3)
                    for _ in range(3):
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(1.5)

                    cards = await page.evaluate("""() => {
                        const r = [];
                        document.querySelectorAll('.job-search-card,[data-entity-urn*="jobPosting"]').forEach(c => {
                            const t = c.querySelector('h3,[class*="title"]');
                            const co = c.querySelector('h4,[class*="company"]');
                            const loc = c.querySelector('[class*="location"]');
                            const a = c.querySelector('a[href*="/jobs/view/"]');
                            const dt = c.querySelector('time');
                            if (t && a) r.push({
                                title: t.innerText.trim(),
                                company: co ? co.innerText.trim() : '',
                                location: loc ? loc.innerText.trim() : '',
                                url: a.href.split('?')[0],
                                posted: dt ? (dt.getAttribute('datetime') || '') : '',
                            });
                        });
                        return r;
                    }""")

                    for c in cards:
                        if not is_pm_title(c.get("title", "")):
                            continue
                        u = c.get("url", "")
                        if u in seen:
                            continue
                        seen.add(u)
                        jid = u.rstrip("/").split("-")[-1]
                        posted = (c.get("posted") or DATE)[:10]
                        jobs.append({
                            "id": f"linkedin-{jid}",
                            "source": "linkedin",
                            "title": c["title"],
                            "company": c.get("company", "").strip(),
                            "location": c.get("location", "").strip(),
                            "remote": True,
                            "salary_text": "", "salary_min": None, "salary_max": None,
                            "posted_date": posted,
                            "apply_url": u,
                            "description": "",
                            "source_query": query,
                            "scraped_at": datetime.now().isoformat(),
                        })
                except Exception as e:
                    print(f"    Playwright error '{query}': {e}")

            await browser.close()
        return jobs

    import asyncio
    return asyncio.run(_scrape())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=100)
    args = parser.parse_args()

    Path("data/jobs-raw").mkdir(parents=True, exist_ok=True)

    # Rule: LinkedIn always uses Playwright (Apify actors don't reliably scrape LinkedIn search results)
    print("LinkedIn scraper — Playwright (fast, card-level data)")
    jobs = scrape_playwright_fallback(args.max)

    # Dedup by ID
    seen, final = set(), []
    for j in jobs:
        if j["id"] not in seen:
            seen.add(j["id"])
            final.append(j)

    with open(OUT_FILE, "w") as f:
        json.dump(final, f, indent=2)

    desc_count = sum(1 for j in final if j.get("description"))
    salary_count = sum(1 for j in final if j.get("salary_text"))
    print(f"\nLinkedIn: {len(final)} PM jobs saved to {OUT_FILE}")
    print(f"  With description: {desc_count} | With salary: {salary_count}")


if __name__ == "__main__":
    main()
