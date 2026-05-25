# Job Hunter — Roadblocks & Pending Fixes

Track items that are broken, partial, or need debugging.

_Last updated: 2026-05-25_

---

## M2 — Search (Scrapers) 🔴 IN PROGRESS

### 🔴 BROKEN — Needs Fix

| # | Source | Issue | File | Notes |
|---|--------|-------|------|-------|
| 1 | **YC Jobs** | 0 jobs returned — Playwright selector broken | `scripts/scrapers/scrape_yc.py` | Try `waitForSelector` on job card class. Run `--headless false` to inspect live HTML. |
| 2 | **Himalayas** | API `title=` param ignores filter — returns 107k unrelated jobs | `scripts/scrapers/scrape_himalayas.py` | Try `?q=product+manager` or client-side filter. May need Playwright fallback. |
| 3 | **LinkedIn** | Apify `run-sync` times out (3min+). Async stays RUNNING beyond 20 polls. | `scripts/scrapers/scrape_linkedin.py` | Script not yet written. Try actor `JkfTWxtpgfvcRQn3p` (Rapid LinkedIn) or increase poll to 30s×30. |

### 🟡 PARTIAL — Works But Needs Improvement

| # | Source | Issue | File | Notes |
|---|--------|-------|------|-------|
| 4 | **Indeed** | Company name blank — JS-rendered, selector mismatch | `scripts/scrapers/scrape_indeed.py` | Use Apify actor `valig/indeed-jobs-scraper` — company in `employer.name`. Merge Apify+Playwright. |
| 5 | **Indeed** | Bot protection kills queries 2–5. Only 11 jobs vs 50+ expected. | `scripts/scrapers/scrape_indeed.py` | Random delays 3–8s, rotate user-agent. Or go Apify-primary. |
| 6 | **RemoteOK** | Tag filter too loose — "product" catches Designer/SDR/Dev roles | `scripts/scrapers/scrape_remoteok.py` | Require "product manager" in title OR ("product" in tags AND "manager" in title). |

### 🟢 NOT YET WRITTEN — Scripts Missing

| # | Source | Skill File | Script Needed |
|---|--------|-----------|---------------|
| 7 | **LinkedIn** | `skills/search/linkedin.md` ✅ | `scripts/scrapers/scrape_linkedin.py` |
| 8 | **Glassdoor** | `skills/search/glassdoor.md` ✅ | `scripts/scrapers/scrape_glassdoor.py` |
| 9 | **Wellfound** | `skills/search/wellfound.md` ✅ | `scripts/scrapers/scrape_wellfound.py` |
| 10 | **Builtin** | `skills/search/builtin.md` ✅ | `scripts/scrapers/scrape_builtin.py` |
| 11 | **Company Direct** | `skills/search/company-direct.md` ✅ | `scripts/scrapers/scrape_company_direct.py` |

---

## M2 — Infrastructure

| # | Item | Status | Fix |
|---|------|--------|-----|
| 12 | ~~`daily-scan.sh` uses `python3` not venv~~ | ✅ FIXED | Now uses `$PROJECT_DIR/venv/bin/python` |
| 13 | ~~Cron not set up~~ | ✅ FIXED | 11pm daily digest cron installed |
| 14 | ~~`scripts/scrapers/` paths missing in daily-scan.sh~~ | ✅ FIXED | All paths correct, graceful skip if missing |
| 15 | **No deduplication across sources** | 🔴 Open | Need global dedup in `score_jobs.py` — hash on `(title + company + location)` |
| 16 | ~~daily-scan.sh calls Telegram~~ | ✅ FIXED | Updated to use `notify_slack.py` |

---

## ✅ RESOLVED — M3/M4/M5/M6

| Milestone | Status |
|-----------|--------|
| M3 Score & Filter | ✅ COMPLETE — `score_jobs.py`, skill files done |
| M4 Notify | ✅ COMPLETE — `notify_slack.py` alert + digest modes |
| M5 Outreach & Apply | ✅ COMPLETE — all skill files + `outreach_apply.py` |
| M6 Track & Follow-up | ✅ COMPLETE — `log_application.py`, `export-tracker.py` (daily tabs) |

---

## Open — Cross-Cutting

| # | Item | Priority | Notes |
|---|------|----------|-------|
| 17 | `ANTHROPIC_API_KEY` not set | 🟡 Medium | Needed for Claude AI drafting in M5. Templates work without it. |
| 18 | `APIFY_API_TOKEN` not set | 🔴 High | Needed for LinkedIn/Indeed/Glassdoor/Wellfound scrapers |
| 19 | Dedup across sources | 🟡 Medium | Same job on Indeed + LinkedIn = duplicate score entries |
| 20 | 8am daily scan cron not installed | 🟡 Medium | Only 11pm digest cron installed. Need: `0 8 * * * /bin/bash .../daily-scan.sh` |
