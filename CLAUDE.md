# Job Hunter — Master Context for Claude Code

## Who I Am

- **Name:** Lucky Chauhan
- **Email:** lucky.raajc@gmail.com
- **Phone:** 857-313-1707
- **Location:** Indiana, USA (EDT — Eastern Daylight Time)
- **LinkedIn:** linkedin.com/in/luckychauhan
- **Visa:** H1B sponsorship required

## Job Search Parameters

- **Target roles:** Product Manager, Senior PM, APM, Platform PM, AI PM
- **Locations:** Remote,anywhere in the USA
- **Minimum salary:** $120,000 USD/year
- **Visa sponsorship:** REQUIRED — skip any job that doesn't sponsor H1B
- **Experience level:** 11+ years (apply to Senior PM, PM, APM depending on company stage)

## My Resume

See `data/my-resume.md` for full resume.

**Key strengths to match against JDs:**

- AI/LLM product experience (knowledge platform, 78% adoption, hallucination metrics)
- Enterprise platform PM ($20M+ programs, 5,000+ users)
- Supply chain + SAP S/4HANA domain depth
- Data analytics (SQL, Python)
- PMP + CSM certified

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

## Cron Schedule

- Daily scan: 8:00 AM EDT
- Deadline check: every 2 hours during business hours

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

- `outputs/tracker.xlsx` — auto-exported from applications.json
- `outputs/resumes/` — tailored resumes per job
- `outputs/cover-letters/` — cover letters per job
- `outputs/outreach/` — drafted outreach messages

## Job Sources

| Source | Script | Skill | Status |
|--------|--------|-------|--------|
| LinkedIn | `scripts/scrapers/scrape_linkedin.py` | `skills/search/linkedin.md` | 🔴 Not written |
| Indeed | `scripts/scrapers/scrape_indeed.py` | `skills/search/indeed.md` | 🟡 Partial (bot protection) |
| Glassdoor | `scripts/scrapers/scrape_glassdoor.py` | `skills/search/glassdoor.md` | 🔴 Not written |
| Wellfound | `scripts/scrapers/scrape_wellfound.py` | `skills/search/wellfound.md` | 🔴 Not written |
| Himalayas | `scripts/scrapers/scrape_himalayas.py` | — | 🟡 Partial (filter broken) |
| RemoteOK | `scripts/scrapers/scrape_remoteok.py` | — | 🟡 Partial (tag filter loose) |
| YC Jobs | `scripts/scrapers/scrape_yc.py` | `skills/search/ycombinator.md` | 🔴 Selector broken |
| Hiring Cafe | `scripts/scrapers/scrape_hiring_cafe.py` | `skills/search/hiring-cafe.md` | ✅ Built |
| Levels.fyi | — | `skills/search/levels-fyi.md` | 🔴 Not written |
| Builtin | — | `skills/search/builtin.md` | 🔴 Not written |
| Company Direct | — | `skills/search/company-direct.md` | 🔴 Not written |
| Niche Boards | — | `skills/search/niche-boards.md` | 🔴 Not written |

## Project Status

- M1 Foundation: COMPLETE
- M2 Search: NOT STARTED
- M3 Score & Filter: COMPLETE
- M4 Notify: COMPLETE
- M5 Outreach & Apply: COMPLETE
- M6 Track & Follow-up: COMPLETE
