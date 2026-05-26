"""
LinkedIn Job Description Enricher — Firecrawl
Reads:  data/jobs-raw/linkedin-YYYY-MM-DD.json  (Playwright card scrape, no descriptions)
Writes: same file — updates description + salary fields for top N jobs
        data/jobs-raw/linkedin-enriched-YYYY-MM-DD.json  (backup)

Strategy:
  - Only enrich jobs with empty description (saves credits)
  - Max 20 jobs per run (conserve free tier 500 credits/month)
  - Skip if FIRECRAWL_API_KEY not set

Usage:
  python scripts/enrich_linkedin.py              # enrich today's file, top 20
  python scripts/enrich_linkedin.py --max 10     # enrich top 10
  python scripts/enrich_linkedin.py --date 2026-05-25
"""
import os, json, re, argparse, time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATE = datetime.now().strftime("%Y-%m-%d")
FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY", "")


def parse_salary(text: str):
    if not text:
        return None, None
    nums = re.findall(r"[\d,]+", text.replace("K", "000").replace("k", "000"))
    nums = [int(n.replace(",", "")) for n in nums if int(n.replace(",", "")) > 1000]
    if len(nums) >= 2:
        return min(nums), max(nums)
    elif len(nums) == 1:
        return nums[0], nums[0]
    return None, None


def extract_salary_from_text(text: str) -> str:
    """Pull salary range from scraped page text."""
    patterns = [
        r"\$[\d,]+[Kk]?\s*[-–]\s*\$[\d,]+[Kk]?(?:\s*/\s*(?:yr|year|annually))?",
        r"\$[\d,]+[Kk]?\s*(?:per year|\/year|\/yr|annually)",
        r"[\d,]+[Kk]?\s*[-–]\s*[\d,]+[Kk]?\s*(?:USD|usd)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return ""


def scrape_job_page(client, url: str) -> dict:
    """Scrape a LinkedIn job page via Firecrawl, return description + salary."""
    try:
        result = client.scrape_url(
            url,
            formats=["markdown"],
            only_main_content=True,
            timeout=20000,
        )
        # firecrawl-py returns ScrapeResponse object or dict
        if hasattr(result, 'markdown'):
            text = result.markdown or ""
        elif isinstance(result, dict):
            text = result.get("markdown") or result.get("content") or ""
        else:
            text = str(result)

        # Trim to reasonable size
        description = text[:8000].strip()
        salary_text = extract_salary_from_text(description)
        salary_min, salary_max = parse_salary(salary_text)

        return {
            "description": description,
            "salary_text": salary_text,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "enriched": True,
        }
    except Exception as e:
        return {"enriched_error": str(e)}


def enrich(date: str, max_jobs: int):
    if not FIRECRAWL_KEY:
        print("✗ FIRECRAWL_API_KEY not set in .env — skipping enrichment")
        return

    raw_file = BASE_DIR / "data" / "jobs-raw" / f"linkedin-{date}.json"
    if not raw_file.exists():
        print(f"✗ LinkedIn file not found: {raw_file}")
        return

    jobs = json.loads(raw_file.read_text())
    # Only enrich jobs with no description
    to_enrich = [j for j in jobs if not j.get("description")][:max_jobs]

    if not to_enrich:
        print(f"✓ All {len(jobs)} LinkedIn jobs already have descriptions")
        return

    print(f"Firecrawl enrichment — {len(to_enrich)} LinkedIn jobs (max {max_jobs})")
    print(f"  Remaining credits used: ~{len(to_enrich)} of 500/month free tier")

    try:
        from firecrawl import FirecrawlApp
        client = FirecrawlApp(api_key=FIRECRAWL_KEY)
    except Exception as e:
        print(f"✗ Firecrawl init error: {e}")
        return

    enriched_count = 0
    salary_count = 0

    # Build lookup by job ID
    jobs_by_id = {j["id"]: j for j in jobs}

    for i, job in enumerate(to_enrich):
        url = job.get("apply_url", "")
        if not url:
            continue

        print(f"  [{i+1}/{len(to_enrich)}] {job.get('company')} — {job.get('title')[:50]}")
        result = scrape_job_page(client, url)

        if result.get("enriched"):
            jobs_by_id[job["id"]].update(result)
            enriched_count += 1
            if result.get("salary_text"):
                salary_count += 1
                print(f"    ✓ description={len(result['description'])} chars | salary={result['salary_text']}")
            else:
                print(f"    ✓ description={len(result['description'])} chars | salary=not found")
        else:
            print(f"    ✗ {result.get('enriched_error','unknown error')}")

        # Rate limit — Firecrawl free tier: 20 req/min
        if i < len(to_enrich) - 1:
            time.sleep(3)

    # Write back enriched data
    final = list(jobs_by_id.values())
    raw_file.write_text(json.dumps(final, indent=2))

    # Also save enriched backup
    backup = BASE_DIR / "data" / "jobs-raw" / f"linkedin-enriched-{date}.json"
    backup.write_text(json.dumps(final, indent=2))

    print(f"\n✓ Enriched {enriched_count}/{len(to_enrich)} jobs")
    print(f"  Salary found: {salary_count}")
    print(f"  Written: {raw_file}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=20, help="Max jobs to enrich (default 20)")
    parser.add_argument("--date", type=str, default=DATE, help="Date of linkedin file (YYYY-MM-DD)")
    args = parser.parse_args()
    enrich(args.date, args.max)


if __name__ == "__main__":
    main()
