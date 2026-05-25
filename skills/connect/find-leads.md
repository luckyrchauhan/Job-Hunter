# Skill: find-leads

## Purpose
Find recruiter + hiring manager for a scored job. Output saved to `data/leads.json`.

## When to Use
Job has `score >= 6` and passed visa check. Run before drafting outreach.

## Inputs
- `job_id` — from `data/jobs-scored.json`
- `company` — company name
- `role_title` — job title

## Process

### Step 1 — Check existing leads
```python
# Check data/leads.json for existing entry for this company
# If recruiter AND hiring_manager both found → skip, return existing
```

### Step 2 — LinkedIn Search (primary)
Search LinkedIn for:
1. **Recruiter/Talent Acquisition:**
   - Query: `"[company]" recruiter "product manager" site:linkedin.com`
   - OR: `"[company]" "talent acquisition" OR "technical recruiter" site:linkedin.com`
   - Target: TA/HR roles with "recruiter" or "talent" in title
2. **Hiring Manager:**
   - Query: `"[company]" "product manager" director OR VP OR "group PM" site:linkedin.com`
   - Target: Senior PM, Director of PM, VP Product — whoever would manage this role

### Step 3 — Apollo.io fallback (if LinkedIn blank)
- Use Apollo free tier: `https://api.apollo.io/v1/people/search`
- Search by company domain + job title keywords
- Extract: name, title, email (if available), LinkedIn URL

### Step 4 — Warmth scoring
Rate each contact 1–3:
- `3` = shared connection / alumni (BU MBA, GlobalLogic, GyanSys, Anglo-Eastern)
- `2` = mutual connections or same industry background
- `1` = cold — no shared context

### Step 5 — Write to leads.json
```json
{
  "company": "Stripe",
  "job_id": "stripe-senior-pm-2026-05-25",
  "recruiter": {
    "name": "Jane Doe",
    "title": "Technical Recruiter",
    "linkedin": "linkedin.com/in/janedoe",
    "email": null,
    "warmth": 1
  },
  "hiring_manager": {
    "name": "John Smith",
    "title": "Director of Product",
    "linkedin": "linkedin.com/in/johnsmith",
    "email": null,
    "warmth": 2
  },
  "found_at": "2026-05-25T10:00:00Z"
}
```

## Output
- Updates `data/leads.json` — appends or updates entry for company
- Returns lead dict for pipeline use

## Notes
- No leads found after both sources → log `"leads_not_found": true`, still proceed
- Priority: recruiter first (faster path), hiring manager second (higher value)
- Never store or send outreach without Lucky's review
