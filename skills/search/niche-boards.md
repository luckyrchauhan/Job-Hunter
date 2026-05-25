# Skill: Search Niche Job Boards

## Purpose
Scrape PM-specific and tech-specific niche boards missed by major aggregators.

## Boards Covered
1. **Pragmatic Institute Jobs** — https://jobs.pragmaticinstitute.com
2. **Mind the Product Jobs** — https://jobs.mindtheproduct.com
3. **Product Hunt Jobs** — https://www.producthunt.com/jobs?category=product
4. **Remote.co PM** — https://remote.co/remote-jobs/product/
5. **We Work Remotely PM** — https://weworkremotely.com/categories/remote-management-product-jobs
6. **Remote OK PM** — https://remoteok.com/remote-product-jobs
7. **Himalayas PM** — https://himalayas.app/jobs/product-management
8. **Otta** — https://app.otta.com (PM filter)
9. **Pallet** — various curated PM job boards
10. **Lenny's Job Board** — https://lennys.com/jobs (PM community)

## Steps

### 1. We Work Remotely (Playwright)
```python
async def scrape_wwr():
    url = "https://weworkremotely.com/categories/remote-management-product-jobs"
    # GET HTML, parse with BeautifulSoup
    # Selector: section.jobs li
    # Fields: title, company, url, date
```

### 2. Remote OK (JSON API)
```python
import requests

def scrape_remoteok():
    url = "https://remoteok.com/api"
    headers = {"User-Agent": "Mozilla/5.0"}
    jobs = requests.get(url, headers=headers).json()
    # Filter: tag "product" or "manager" in tags list
    pm_jobs = [j for j in jobs if any(
        t in ["product", "product manager", "pm"] 
        for t in j.get("tags", [])
    )]
    return pm_jobs
```

### 3. Himalayas (JSON API)
```python
def scrape_himalayas():
    url = "https://himalayas.app/jobs/product-management.json"
    resp = requests.get(url, timeout=30)
    return resp.json().get("jobs", [])
```

### 4. Normalize All Sources
```json
{
  "id": "<board>-<job_id>",
  "source": "<board_name>",
  "title": "",
  "company": "",
  "location": "Remote",
  "remote": true,
  "salary_min": null,
  "salary_max": null,
  "posted_date": "",
  "apply_url": "",
  "description": "",
  "scraped_at": "ISO timestamp"
}
```

### 5. Save Output
Write each board to `data/jobs-raw/niche-<board>-YYYY-MM-DD.json`
Or combine: `data/jobs-raw/niche-boards-YYYY-MM-DD.json`

## Notes
- Niche boards often have less competition than LinkedIn
- Remote OK API is free and clean — prioritize it
- Himalayas explicitly shows visa sponsorship per listing — capture this
- Mind the Product and Lenny's boards skew toward PM-forward companies
