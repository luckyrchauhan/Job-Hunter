# Skill: Search Levels.fyi Jobs

## Purpose
Scrape Levels.fyi job board. Best source for salary-transparent PM roles at tech companies.

## Target URL
```
https://www.levels.fyi/jobs/?jobFamily=PM&country=254
```
(country=254 = USA)

## Steps

### 1. API Discovery
Levels.fyi has an internal API. Use it directly:

```python
import requests

def scrape_levels_fyi():
    # Internal API endpoint (discovered via browser devtools)
    url = "https://www.levels.fyi/js/jobsData.json"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Referer": "https://www.levels.fyi/jobs/"
    }
    
    resp = requests.get(url, headers=headers, timeout=30)
    all_jobs = resp.json()
    
    # Filter for PM roles in USA
    pm_jobs = [
        j for j in all_jobs
        if "product manager" in j.get("title", "").lower()
        and j.get("country") == "US"
    ]
    return pm_jobs
```

### 2. Playwright Fallback
If JSON endpoint unavailable:
```
URL: https://www.levels.fyi/jobs/?jobFamily=PM&country=254
Selector: .job-card or [data-testid="job-card"]
```

### 3. Normalize Fields
```json
{
  "id": "levels-<job_id>",
  "source": "levels_fyi",
  "title": "",
  "company": "",
  "location": "",
  "remote": true/false,
  "salary_min": null,
  "salary_max": null,
  "total_comp_min": null,
  "total_comp_max": null,
  "level": "L4/L5/L6 etc",
  "posted_date": "",
  "apply_url": "",
  "description": "",
  "scraped_at": "ISO timestamp"
}
```

### 4. Save Output
Write to `data/jobs-raw/levels-fyi-YYYY-MM-DD.json`

## Notes
- Levels.fyi has best salary + TC (total comp) data — always capture
- Most companies here are Tier 1/2 H1B sponsors
- `level` field maps to: L3-L4 = APM/PM, L5 = Senior PM, L6+ = Principal/Director
