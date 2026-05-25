# Job Hunter — Product Requirements Document

**Version:** 1.0  
**Date:** 2026-05-25  
**Owner:** Your Name (your.email@example.com)  
**Status:** Ready to Build

---

## 1. Problem Statement

Job searching across multiple platforms (LinkedIn, Indeed, Glassdoor, Wellfound, niche boards) is manual, time-consuming, and error-prone. Good opportunities are missed because:

- No single place aggregates all relevant jobs
- No automated relevance filtering against personal profile
- Referral outreach is slow and inconsistent
- Application deadlines are missed
- Follow-ups are forgotten

**Goal:** A fully automated, AI-powered job hunting system that finds, scores, and helps apply to PM roles — with the human only needed at the final apply step.

---

## 2. Target User

**Your Name** — Product Manager actively job searching.

### Profile (TO BE FILLED before first run)

```yaml
name: Your Name
email: your.email@example.com
target_role: Product Manager
experience_level: [Senior PM / APM/ PM] # ← fill this
locations: [Remote, anywhere in the USA] # ← fill this
visa_sponsorship_required: true # ← fill this (H1B?)
minimum_salary_usd: 120000 # ← fill this
dream_companies: [] # ← fill this
blocklist_companies: [] # ← fill this
```

---

## 3. System Overview

A Python-based automation system controlled via Claude Code. Runs on scheduled cron jobs (8am, 12pm, 3pm EDT) plus a lightweight watcher every 15 minutes for instant high-match alerts. No manual intervention required except final application submission.

### High-Level Flow

```
[Cron 8am / 12pm / 3pm]
    → Scrapers collect jobs from all sources
    → Deduplication & normalization
    → Claude AI scores each job (1-10) vs resume
    → Visa check & blocklist filter
    → Urgency flagging (apply-now / this-week / monitor / stale)
    → Lead finding (recruiter + hiring manager per company)
    → Claude drafts outreach messages & cover letters
    → Tracker updated (applications.json → Google Sheets live sync)
    → Slack digest sent with top matches

[Watcher — every 15min, 8am–8pm EDT]
    → Quick-scrape new postings only (delta)
    → Score new jobs
    → IF score ≥ 8 AND posted < 2hrs AND applicants < 50:
        → Instant Slack alert (no waiting for scheduled scan)
        → Draft materials + sync Google Sheet
```

---

## 4. Project Structure

```
job-hunter/
│
├── .env                         ← API keys (never committed)
├── .env.example                 ← Safe key template
├── .gitignore                   ← Excludes .env, raw data, cookies
├── CLAUDE.md                    ← Master memory: resume, rules, workflow
│
├── .claude/
│   └── settings.json            ← MCP connections (Apify, Telegram, etc.)
│
├── config/
│   ├── search-params.json       ← Keywords, salary floor, posting age, sources toggle
│   ├── target-companies.json    ← Watchlists: dream companies, maritime, startups
│   ├── score-weights.json       ← Tunable weights: domain fit, visa, salary, seniority
│   └── blocklist.json           ← Companies confirmed no sponsorship — auto-skip
│
├── skills/
│   ├── search/
│   │   ├── linkedin.md          ← Scrape via Apify LinkedIn Jobs Scraper
│   │   ├── indeed.md            ← Scrape via Apify Indeed Scraper
│   │   ├── glassdoor.md         ← Scrape via Apify Glassdoor Scraper
│   │   ├── wellfound.md         ← Scrape via Apify Wellfound Scraper
│   │   ├── levels-fyi.md        ← Scrape Levels.fyi for salary-verified PM roles
│   │   ├── builtin.md           ← Scrape Builtin.com for tech/startup PM roles
│   │   ├── ycombinator.md       ← Scrape YC Work at a Startup board
│   │   ├── niche-boards.md      ← gCaptain, WorkBoat, ShippingJobs, PortStrategy
│   │   └── company-direct.md   ← Browser agent fetches career pages from target-companies.json
│   ├── score/
│   │   ├── fit-score.md         ← Claude scores 1-10 vs my-resume.md + score-weights.json
│   │   ├── visa-check.md        ← Validate sponsorship via h1bdata.info + job description
│   │   └── urgency-flag.md      ← apply-now (<2d), this-week (<7d), monitor, stale
│   ├── connect/
│   │   ├── find-leads.md        ← Find recruiter + hiring manager via LinkedIn/Apollo
│   │   ├── referral-ask.md      ← Draft warm referral message (alumni/shared background)
│   │   └── cold-outreach.md     ← Draft cold message when no warm lead exists
│   ├── apply/
│   │   ├── tailor-resume.md     ← Rewrite resume to match JD keywords
│   │   ├── cover-letter.md      ← Generate cover letter from JD + tailored resume
│   │   └── submit-checklist.md  ← Pre-apply QA: visa confirmed, score ≥6, resume saved
│   └── track/
│       ├── log-application.md   ← Write to applications.json + export tracker.xlsx
│       └── followup.md          ← Draft follow-up by timeline (1w, 2w, no-response close)
│
├── data/
│   ├── my-resume.md             ← Single source of truth — master resume
│   ├── jobs-raw/                ← Unprocessed scrape output per source per run
│   ├── jobs-scored.json         ← Normalized + scored master job list
│   ├── leads.json               ← Contacts found per company with warmth rating
│   └── applications.json        ← Full log: status, dates, contacts, outcomes
│
├── outputs/
│   ├── tracker.xlsx             ← Auto-generated Excel tracker after every run
│   ├── resumes/                 ← Tailored resume saved per role (e.g. google-pm-2026-05-25.md)
│   ├── cover-letters/           ← Cover letter saved per role
│   └── outreach/                ← Drafted messages saved per contact
│
└── scripts/
    ├── daily-scan.sh            ← Master pipeline: search → score → notify
    ├── deadline-check.py        ← Flags applications in 5-day apply window
    └── export-tracker.py        ← Converts applications.json → tracker.xlsx
```

---

## 5. Job Sources

| Source               | Method        | Cost                | PM Role Quality           |
| -------------------- | ------------- | ------------------- | ------------------------- |
| LinkedIn             | Apify actor   | Free tier (limited) | ⭐⭐⭐⭐⭐                |
| Indeed               | Apify actor   | Free tier           | ⭐⭐⭐⭐                  |
| Glassdoor            | Apify actor   | Free tier           | ⭐⭐⭐⭐                  |
| Wellfound            | Apify actor   | Free tier           | ⭐⭐⭐⭐ (startups)       |
| Levels.fyi           | Browser agent | Free                | ⭐⭐⭐⭐ (salary data)    |
| Builtin.com          | Browser agent | Free                | ⭐⭐⭐                    |
| YC Jobs              | Browser agent | Free                | ⭐⭐⭐ (early stage)      |
| Company career pages | Browser agent | Free                | ⭐⭐⭐⭐⭐ (direct)       |
| Niche boards         | Browser agent | Free                | ⭐⭐ (maritime/logistics) |

**Scraping strategy:**

- **Apify** for major boards (LinkedIn, Indeed, Glassdoor, Wellfound) — maintained actors, reliable
- **Playwright browser agent** for everything else — free, no API needed

---

## 6. AI Scoring System

Each job is scored **1–10** by Claude against `data/my-resume.md` using weights from `score-weights.json`.

### Default Score Weights

```json
{
  "role_title_match": 0.25,
  "domain_fit": 0.2,
  "skills_match": 0.2,
  "seniority_match": 0.15,
  "salary_match": 0.1,
  "visa_sponsorship": 0.15
}
```

### Score Actions

| Score | Action                                    |
| ----- | ----------------------------------------- |
| 8–10  | Priority apply — urgent notification sent |
| 6–7   | Apply this week                           |
| 4–5   | Monitor — revisit if nothing better       |
| 1–3   | Skip — not logged                         |

---

## 7. Urgency Flagging

Every job gets two signals: **time since posted** and **total applications submitted so far**.

### 7a. Time-Based Urgency Tiers

| Tag                       | Posted Age      | Action                                     |
| ------------------------- | --------------- | ------------------------------------------ |
| 🔴🔴 `apply-now-critical` | < 1 hour ago    | Immediate Telegram alert — drop everything |
| 🔴 `apply-now-hot`        | 1–5 hours ago   | Immediate Telegram alert                   |
| 🟠 `apply-now-today`      | 5–15 hours ago  | Telegram alert within current session      |
| 🟡 `apply-soon-24h`       | 15–24 hours ago | In next daily digest, top of list          |
| 🟡 `apply-soon-1d`        | 1–2 days ago    | In daily digest                            |
| 🟢 `apply-this-week-2d`   | 2–5 days ago    | In daily digest, lower priority            |
| 🔵 `monitor`              | 5–7 days ago    | In daily digest only if score ≥8           |
| ⚫ `stale`                | > 7 days ago    | Skip — not notified                        |

### 7b. Application Count Gate (Notification Filter)

> **Rule:** Only send Telegram notifications if the job has **fewer than 50 applications**. If 50+ applicants have already applied, suppress the notification regardless of urgency tier.

| Applications Count | Notification Behavior                                       |
| ------------------ | ----------------------------------------------------------- |
| < 50 applicants    | ✅ Notify — all urgency tiers apply normally                |
| ≥ 50 applicants    | 🔕 Suppress notification — job still logged but not alerted |

**Note:** Application count is scraped from the listing where available (LinkedIn shows this). If count is unavailable, default to notifying (assume < 50).

### 7c. Combined Logic

```
IF posted < 7 days ago AND applicants < 50:
    → Apply urgency tier + send Telegram notification
IF posted < 7 days ago AND applicants >= 50:
    → Log job, NO notification sent
IF posted > 7 days ago:
    → Mark stale, skip entirely
```

---

## 8. Visa & Blocklist Filtering

**Visa check** (if `visa_sponsorship_required: true`):

1. Scan job description for sponsorship keywords (`H1B`, `will sponsor`, `visa sponsorship`, `work authorization`)
2. Cross-reference company across **all H1B data sources** (checked in parallel)
3. Aggregate confidence score across sources → final tag assigned
4. Jobs tagged `no-sponsorship` → auto-skip + add to blocklist

### H1B Data Sources (checked in parallel)

| Source            | URL            | What it provides                     |
| ----------------- | -------------- | ------------------------------------ |
| H1B Data          | h1bdata.info   | Historical H1B filings by company    |
| H1B Grader        | h1bgrader.com  | Company H1B approval rates + grades  |
| H1B Database      | h1bsalary.info | Salary + filing records              |
| H1B Metrics       | h1bmetrics.com | Trends, approval rates, denial rates |
| MyVisaJobs        | myvisajobs.com | Sponsor history + job listings       |
| USCIS Public Data | uscis.gov      | Official LCA/H1B disclosure data     |

### Sponsorship Confidence Tags

| Tag                 | Criteria                                                      | Action                    |
| ------------------- | ------------------------------------------------------------- | ------------------------- |
| ✅ `confirmed`      | Listed as sponsor on 2+ sources with recent filings           | Proceed                   |
| 🟡 `likely`         | Found on 1 source OR JD says "will sponsor"                   | Proceed with caution note |
| ❓ `unclear`        | No data found, JD silent on visa                              | Flag for manual check     |
| ❌ `no-sponsorship` | JD explicitly says "no sponsorship" OR confirmed deny pattern | Auto-skip + blocklist     |

**Blocklist:** Companies in `blocklist.json` are never shown, never processed.

---

## 9. Outreach & Application Pipeline

When a job scores ≥6 and passes visa check:

1. **Find leads** — recruiter + hiring manager via LinkedIn search
2. **Warm outreach first** — check for alumni, shared connections, shared background
3. **Draft message** — Claude writes referral ask or cold outreach, saved to `outputs/outreach/`
4. **Tailor resume** — Claude rewrites `data/my-resume.md` to match JD keywords
5. **Cover letter** — Claude generates from tailored resume + JD
6. **Submit checklist** — visa ✅, score ≥6 ✅, resume saved ✅
7. **YOU APPLY** — all materials ready, you submit
8. **Log it** — `applications.json` updated, `tracker.xlsx` regenerated

---

## 10. Notifications

### Slack Webhook (Primary)

- **Instant alert** for jobs score ≥ 8 AND posted < 2 hours ago — fires immediately via watcher, does NOT wait for scheduled scan
- **Scheduled digest** at 8:05am, 12:05pm, 3:05pm EDT — top 10 jobs per run with scores
- **Weekly summary** every Monday — pipeline stats, follow-up reminders
- **Follow-up reminders** — "You applied to [Company] 7 days ago — follow up?"

### Instant Alert Logic (watcher.py)

Separate lightweight watcher polls every **15 minutes, 8am–8pm EDT**:
```
[Watcher — every 15min]
    → Quick-scrape new postings only (delta, not full scan)
    → Score each new job
    → IF score ≥ 8 AND posted < 2hrs AND applicants < 50:
        → Immediate Slack alert
        → Draft outreach + tailor resume
        → Update Google Sheet row
```

### Message format example:

```
🔴 APPLY NOW — Score: 9/10
Role: Senior PM — Payments
Company: Stripe
Posted: 45 minutes ago
Salary: $180k–$220k
Visa: ✅ Confirmed sponsor
Apply: [link]
Outreach drafted: outputs/outreach/stripe-pm-2026-05-25.md
```

---

## 11. Tracking

**Source of truth:** `data/applications.json`

```json
{
  "id": "stripe-senior-pm-2026-05-25",
  "company": "Stripe",
  "role": "Senior PM — Payments",
  "score": 9,
  "urgency": "apply-now",
  "visa": "confirmed",
  "status": "applied",
  "applied_date": "2026-05-25",
  "outreach_contact": "Jane Doe (Recruiter)",
  "outreach_sent": true,
  "follow_up_due": "2026-06-01",
  "outcome": null
}
```

**Live-synced to:** Google Sheets via Sheets API after every run and every status change.
- Sheet ID stored in `.env` as `GOOGLE_SHEET_ID`
- Auth via Google Service Account: `.env` → `GOOGLE_SERVICE_ACCOUNT_JSON`
- Lucky can view/filter/sort anytime from phone or browser
- Manual notes/edits by Lucky in the sheet are **not overwritten** by system (system only appends/updates its own columns)
- `outputs/tracker.xlsx` kept as local backup export

---

## 12. CLAUDE.md — Master Memory

The `CLAUDE.md` file at the root tells Claude Code everything it needs:

- Full resume (copy of `data/my-resume.md`)
- Job search rules (min score, visa requirement, blocklist logic)
- Workflow order (search → score → visa → leads → draft → notify → log)
- Skill file locations and when to use each
- Output naming conventions
- Never-do rules (never apply automatically, never commit `.env`)

---

## 13. APIs & Tools Required

| Tool             | Purpose                               | Cost                  | Get it at              |
| ---------------- | ------------------------------------- | --------------------- | ---------------------- |
| Apify            | Job scraping (LinkedIn, Indeed, etc.) | Free tier (5 runs/mo) | apify.com              |
| Playwright       | Browser agent for direct scraping     | Free                  | pip install playwright |
| Telegram Bot API | Notifications                         | Free                  | t.me/BotFather         |
| h1bdata.info     | Visa sponsorship lookup               | Free (web scrape)     | h1bdata.info           |
| Claude API       | AI scoring + drafting                 | Covered by Pro plan   | Already have           |

**Optional (add later):**
| Tool | Purpose | Cost |
|------|---------|------|
| Apollo.io | Find recruiter emails | Free tier |
| Slack webhook | Alternative to Telegram | Free |
| Notion API | Visual dashboard | Free tier |

---

## 14. Build Order (Milestones)

### Milestone 1 — Foundation (Day 1) ✅ COMPLETE

- [x] Set up project structure (all folders + files)
- [x] Write `CLAUDE.md` with resume + rules
- [x] Write `config/` JSON files with defaults
- [x] Set up `.env` + `.gitignore`
- [x] Init git repo
- [x] Extract resume into `data/my-resume.md`

### Milestone 2 — Search (Day 2–3)

- [ ] Write `skills/search/linkedin.md` skill
- [ ] Write `skills/search/indeed.md` skill
- [ ] Set up Apify account + get free API key
- [ ] Test scraping — get raw jobs into `data/jobs-raw/`
- [ ] Add 2–3 more sources (Glassdoor, Wellfound, company-direct)

### Milestone 3 — Score & Filter (Day 3–4)

- [ ] Write `data/my-resume.md` (your full resume)
- [ ] Write `skills/score/fit-score.md` skill
- [ ] Write `skills/score/visa-check.md` skill
- [ ] Write `skills/score/urgency-flag.md` skill
- [ ] Test: 20 jobs in → scored + filtered output

### Milestone 4 — Notify (Day 4–5)

- [ ] Create Telegram bot (5 mins via BotFather)
- [ ] Write notification script
- [ ] Test daily digest format
- [ ] Set up cron jobs (8am, 12pm, 3pm daily) + watcher every 15min

### Milestone 5 — Outreach & Apply (Day 5–7)

- [ ] Write `skills/connect/find-leads.md`
- [ ] Write `skills/connect/referral-ask.md`
- [ ] Write `skills/apply/tailor-resume.md`
- [ ] Write `skills/apply/cover-letter.md`
- [ ] Write `skills/apply/submit-checklist.md`
- [ ] Test end-to-end: 1 job → leads → draft → ready to apply

### Milestone 6 — Track & Follow-up (Day 7)

- [ ] Write `skills/track/log-application.md`
- [ ] Write `scripts/export-tracker.py`
- [ ] Write `skills/track/followup.md`
- [ ] Test: apply → log → Excel updated → follow-up reminder

---

## 15. Open Questions (Fill Before Build)

These are not blockers but improve accuracy from day one:

| Question                           | Status               |
| ---------------------------------- | -------------------- |
| Resume (Word/PDF/text)             | ⬜ Needed            |
| Target locations                   | ⬜ Needed            |
| Visa sponsorship needed?           | ⬜ Needed            |
| Minimum salary                     | ⬜ Needed            |
| Dream companies list               | ⬜ Optional          |
| Experience level (Senior/APM/etc.) | ⬜ Needed            |
| Telegram account exists?           | ⬜ Needed            |
| Time zone                          | ⬜ Needed (for cron) |

---

## 16. What Claude Code Does vs What You Do

| Task                      | Who Does It                |
| ------------------------- | -------------------------- |
| Find & scrape jobs        | 🤖 Claude Code (automated) |
| Score jobs vs resume      | 🤖 Claude Code (automated) |
| Visa check                | 🤖 Claude Code (automated) |
| Flag urgency              | 🤖 Claude Code (automated) |
| Find recruiter/HM         | 🤖 Claude Code (automated) |
| Draft outreach message    | 🤖 Claude Code (automated) |
| Tailor resume             | 🤖 Claude Code (automated) |
| Draft cover letter        | 🤖 Claude Code (automated) |
| Send Telegram alert       | 🤖 Claude Code (automated) |
| Update tracker            | 🤖 Claude Code (automated) |
| **Review & hit Apply**    | **👤 You**                 |
| **Send outreach message** | **👤 You (review first)**  |

---

_PRD written by Claude Code — Job Hunter v1.0_
