# Job Hunter — Master Context for Claude Code

## Who I Am

- **Name:** Your Name
- **Email:** your.email@example.com
- **Phone:** 555-000-0000
- **Location:** Indiana, USA (EDT — Eastern Daylight Time)
- **LinkedIn:** linkedin.com/in/your-profile
- **Visa:** H1B sponsorship required

## Job Search Parameters

- **Target roles:** Product Manager, PM, APM, Platform PM, AI PM
- **Locations:** Remote, anywhere in the USA
- **Minimum salary:** $120,000 USD/year
- **Visa sponsorship:** REQUIRED — skip any job that doesn't sponsor H1B
- **PM Experience level:** 3-5years (apply to PM, PM, APM depending on company stage)
- **Total Experience level:** 11 years which include non-pm role

## My Resume

See `data/my-resume.md` for full resume.

**Key strengths to match against JDs:**

- AI/LLM product experience (knowledge platform, 78% adoption, hallucination metrics)
- Enterprise platform PM ($20M+ programs, 5,000+ users)
- Supply chain + SAP S/4HANA domain depth
- Data analytics (SQL, Python)
- PMP + CSM certified
- MBA
- MS in Digital technology

## Scoring Weights

See `config/score-weights.json` for full weights.

**High-value signals:**

- AI/LLM/Generative AI in JD → +2 points
- Enterprise platform or supply chain → +1.5 points
- Remote or Boston → +1 point
- H1B sponsored confirmed → mandatory
- Salary ≥ $120k → mandatory

## Never Do

- NEVER apply automatically — I (Lucky) do the final submit
- NEVER commit `.env` to git
- NEVER store credentials in any tracked file
- NEVER skip visa sponsorship check
- NEVER send outreach without my review

## Scraper Rules

### Method per source (DO NOT change without testing)

| Source | Primary | Fallback 1 | Fallback 2 | Cost tier |
|--------|---------|------------|------------|-----------|
| LinkedIn | Playwright | — | — | Free |
| Indeed | Apify `MXLpngmVpE8WTESQr` | JobSpy (python-jobspy) | Playwright | Apify paid → JobSpy free |
| Glassdoor | Apify `vKjDv4zCNPfku2byp` | JobSpy | — | Apify paid → JobSpy free (Cloudflare blocks both when Apify down) |
| Wellfound | Apify actor | Playwright | — | Apify paid |
| ZipRecruiter | Apify `bkwSYfgLsyEazgOvf` | JobSpy | — | Apify paid → JobSpy free (Cloudflare blocks both when Apify down) |
| Google Jobs | Apify `CkLDY9GAQf6QlP6GP` | SerpAPI | — | Apify paid → SerpAPI **100/mo limit** |
| Himalayas | Public JSON API | — | — | Free unlimited |
| Hiring Cafe | Public API | — | — | Free unlimited |
| Greenhouse | Free public API `boards-api.greenhouse.io` | — | — | Free unlimited |
| Lever | Free public API `api.lever.co` | — | — | Free unlimited |
| Dice | Playwright | — | — | Free unlimited |
| RemoteOK | Public JSON API | — | — | Free unlimited |
| YC Jobs | Public JSON API | — | — | Free unlimited |
| Builtin | Public API | Playwright | — | Free unlimited |
| Monster | Broken — 403 | — | — | Skip until fixed |
| Firecrawl | **DISABLED** — LinkedIn blocks it | — | — | Do NOT use for LinkedIn |

### Hard rules
- NEVER use Apify for LinkedIn
- NEVER run Apify scrapers in parallel — free tier hits concurrent limit; run sequentially in daily-scan.sh
- NEVER use Firecrawl for LinkedIn job pages — blocked at infrastructure level; 0% success rate
- NEVER run Google Jobs SerpAPI more than once/day — 100 searches/month limit, 2 queries/day = 60/month
- NEVER add new SerpAPI queries without checking monthly budget first
- Apify free tier = ~$5/month compute units; monitor at apify.com/billing; resets monthly
- When Apify limit hit → scrapers auto-fallback (no manual action needed)

### API budgets (monthly free tier)

| API | Limit | Current usage | Rule |
|-----|-------|--------------|------|
| Apify | ~$5 compute | Resets monthly | Primary for Indeed/Glassdoor/ZipRecruiter/GoogleJobs |
| SerpAPI | 100 searches | 2 queries × 1/day × 30 = **60** | Google Jobs morning scan only (8am), 2 queries max |
| Firecrawl | 500 credits | **0** (disabled) | Reserved — do NOT use for LinkedIn; only redirect to Greenhouse/Lever enrichment if needed |
| JobSpy | Unlimited | As needed | Auto-fallback for Indeed/Glassdoor/ZipRecruiter when Apify down |

### Fallback chain (auto, no manual action)
```
Apify (primary)
  └─ 403 / limit hit
       ├─ Indeed      → JobSpy → Playwright
       ├─ Glassdoor   → JobSpy (may also 403 — Cloudflare)
       ├─ ZipRecruiter → JobSpy (may also 403 — Cloudflare)
       └─ Google Jobs  → SerpAPI (morning scan only, 2 queries)
```

## Cron Schedule

- Scheduled scans: **8:00 AM, 12:00 PM, 3:00 PM EDT** (`scripts/daily-scan.sh`)
- Instant watcher: **every 15 minutes, 8am–8pm EDT** (`scripts/watcher.py`) — fires immediate Slack alert for score ≥ 8 + posted < 2hrs, does NOT wait for scheduled scan
- Deadline check: every 2 hours during business hours

### Cron entries (`crontab -e`):
```
0  8 * * * /bin/bash /Users/your-profile/Documents/Projects/Antigravity/Job-Hunter/scripts/daily-scan.sh >> /Users/your-profile/Documents/Projects/Antigravity/Job-Hunter/logs/daily-scan.log 2>&1
0 12 * * * /bin/bash /Users/your-profile/Documents/Projects/Antigravity/Job-Hunter/scripts/daily-scan.sh >> /Users/your-profile/Documents/Projects/Antigravity/Job-Hunter/logs/daily-scan.log 2>&1
0 15 * * * /bin/bash /Users/your-profile/Documents/Projects/Antigravity/Job-Hunter/scripts/daily-scan.sh >> /Users/your-profile/Documents/Projects/Antigravity/Job-Hunter/logs/daily-scan.log 2>&1
*/15 8-20 * * * /Users/your-profile/Documents/Projects/Antigravity/Job-Hunter/venv/bin/python /Users/your-profile/Documents/Projects/Antigravity/Job-Hunter/scripts/watcher.py >> /Users/your-profile/Documents/Projects/Antigravity/Job-Hunter/logs/watcher.log 2>&1
```

## Notification Channel

- Slack webhook (see `.env` for SLACK_WEBHOOK_URL)
- Alert threshold: urgency tier ≤ 3 (Apply Now / <1hr / <5hr / <15hr)

## Skills Location

All Claude Code skills are in `skills/` directory:

- `skills/search/` — job scraping instructions per source
- `skills/score/` — fit scoring, visa check, urgency flagging
- `skills/connect/` — lead finding, referral ask, cold outreach
- `skills/apply/` — resume tailoring, cover letter, submit checklist
- `skills/track/` — logging, follow-up

## Data Files

- `data/my-resume.md` — source of truth for resume
- `data/jobs-raw/` — raw scraped jobs (JSON per source per day)
- `data/jobs-scored.json` — scored + filtered jobs
- `data/leads.json` — recruiters/HMs found per company
- `data/applications.json` — all applications I've submitted

## Output Files

- `outputs/tracker.xlsx` — local Excel backup (auto-exported from applications.json)
- Google Sheets — live tracker, synced via `scripts/sync_sheets.py` after every scan (requires `GOOGLE_SHEET_ID` + `GOOGLE_SERVICE_ACCOUNT_JSON` in `.env`)
- `outputs/resumes/` — tailored resumes per job
- `outputs/cover-letters/` — cover letters per job
- `outputs/outreach/` — drafted outreach messages

## Job Sources

| Source | Script | Skill | Status |
|--------|--------|-------|--------|
| LinkedIn | `scripts/scrapers/scrape_linkedin.py` | `skills/search/linkedin.md` | ✅ Built — needs APIFY_API_TOKEN |
| Indeed | `scripts/scrapers/scrape_indeed.py` | `skills/search/indeed.md` | ✅ Fixed — Apify primary, Playwright fallback |
| Glassdoor | `scripts/scrapers/scrape_glassdoor.py` | `skills/search/glassdoor.md` | ✅ Built — needs APIFY_API_TOKEN |
| Wellfound | `scripts/scrapers/scrape_wellfound.py` | `skills/search/wellfound.md` | ✅ Built — Apify + Playwright fallback |
| Himalayas | `scripts/scrapers/scrape_himalayas.py` | — | ✅ Fixed — remoteOnly param added |
| RemoteOK | `scripts/scrapers/scrape_remoteok.py` | — | ✅ Fixed — title filter tightened |
| YC Jobs | `scripts/scrapers/scrape_yc.py` | `skills/search/ycombinator.md` | ✅ Fixed — JSON API primary + Playwright fallback |
| Hiring Cafe | `scripts/scrapers/scrape_hiring_cafe.py` | `skills/search/hiring-cafe.md` | ✅ Built |
| Levels.fyi | — | `skills/search/levels-fyi.md` | 🔴 Not written (low priority) |
| Builtin | `scripts/scrapers/scrape_builtin.py` | `skills/search/builtin.md` | ✅ Built — API + Playwright fallback |
| Company Direct | `scripts/scrapers/scrape_company_direct.py` | `skills/search/company-direct.md` | ✅ Built — 20 companies, Mondays only |
| Niche Boards | `scripts/scrapers/scrape_niche.py` | `skills/search/niche-boards.md` | ✅ Built — Pallet API + ProductHunt |

## Project Status

- M1 Foundation: ✅ COMPLETE
- M2 Search: ✅ COMPLETE — all scrapers built/fixed; needs APIFY_API_TOKEN to run Apify sources
- M3 Score & Filter: ✅ COMPLETE
- M4 Notify: ✅ COMPLETE
- M5 Outreach & Apply: ✅ COMPLETE
- M6 Track & Follow-up: ✅ COMPLETE

## Remaining Config (not code)

| Item | Priority | Action |
|------|----------|--------|
| `APIFY_API_TOKEN` | 🔴 High | Set in `.env` — enables LinkedIn, Indeed (Apify), Glassdoor, Wellfound |
| `ANTHROPIC_API_KEY` | 🟡 Medium | Set in `.env` — enables AI resume/cover letter drafting (M5). Templates work without it. |
| 8am cron | 🟡 Medium | `crontab -e` → `0 8 * * * /bin/bash /path/to/Job-Hunter/scripts/daily-scan.sh >> /path/to/Job-Hunter/logs/daily-scan.log 2>&1` |
