# Skill: hiring-cafe

## Source
https://hiring.cafe/ — AI-powered job search engine, aggregates from 100s of ATS sources (Greenhouse, Lever, Workday, Breezy, etc.)

## Why
- Aggregates direct company ATS postings (not LinkedIn reposts)
- Structured AI-parsed data: visa_sponsorship, workplace_type, salary, seniority_level
- `visa_sponsorship: true` filter available
- Often has PM roles not on mainstream boards

## Method
Playwright browser automation — search filters are client-side (SSR endpoint ignores query params).

## Search Config
```
URL: https://hiring.cafe/
Filters to apply:
  - Job Title: "product manager"
  - Workplace Type: Remote
  - Visa Sponsorship: true (toggle on)
  - Country: United States
  - Seniority: Mid Level, Senior Level
```

## Script
`scripts/scrapers/scrape_hiring_cafe.py`

## Output Fields (from v5_processed_job_data)
```json
{
  "id": "hiring-cafe-{source}___{board_token}___{job_id}",
  "source": "hiring_cafe",
  "title": "job_information.title",
  "company": "board_token (or company_name if available)",
  "location": "formatted_workplace_location",
  "remote": "workplace_type == 'Remote'",
  "salary_text": "compensation range if available",
  "apply_url": "apply_url",
  "description": "requirements_summary",
  "visa_status": "confirmed if visa_sponsorship==true, unknown otherwise",
  "posted_date": "today (hiring.cafe doesn't expose date reliably)",
  "scraped_at": "ISO timestamp"
}
```

## Notes
- `visa_sponsorship: true` in v5_processed_job_data = Claude-confirmed H1B signal → score as `confirmed`
- `job_category` PM categories: "Product Management", "Technology - Product"
- Filter `workplace_type: "Remote"` for remote jobs
- Rate limit: add 2s delay between page scrolls
- Max 100 jobs per run (hiring.cafe paginates by 40)
