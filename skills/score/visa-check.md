# Skill: visa-check — H1B Sponsorship Verification

## Purpose
Determine H1B sponsorship likelihood for each company. Lucky requires sponsorship — mandatory gate.

## Tier Classification (from config/target-companies.json)

| Tier | Description | Action |
|------|-------------|--------|
| tier_1_heavy_sponsors | 500+ H1B/year. Near-certain. | APPROVED |
| tier_2_consistent_sponsors | 50–500/year. Regular sponsors. | APPROVED |
| tier_3_startup_sponsors | Selective. PM roles often qualify. | LIKELY — flag for manual confirm |
| tier_4_verify_first | Unclear/inconsistent history. | VERIFY — flag, do not discard |
| Not in any tier | Unknown company. | UNKNOWN — check JD |

## Check Logic (in order)

### Step 1: Exact company match
Normalize: lowercase, strip "Inc.", "LLC", "Corp.", "Ltd.", "&" → "and".
Search all 4 tiers. Return tier if found.

### Step 2: Fuzzy match
Check if company name contains or is contained by any tier entry.

### Step 3: JD keyword scan (if still unknown)
Scan description + title for:
- "visa sponsorship available"
- "will sponsor H1B"
- "H1B transfer"
- "OPT/CPT accepted"
→ If found: sponsorship_confirmed: true, visa_status: "jd_confirmed"

### Step 4: Negative signals
Scan for:
- "must be authorized to work"
- "no sponsorship"
- "US citizen or permanent resident only"
- "security clearance required"
→ If found: discard: true, discard_reason: "no_sponsorship"

### Step 5: Unknown fallback
visa_status: "unknown", sponsorship_confirmed: false
Do NOT discard — flag for Lucky's manual review.

## Output Fields
```json
{
  "visa_status": "tier_1 | tier_2 | tier_3 | tier_4 | jd_confirmed | unknown | no_sponsorship",
  "sponsorship_confirmed": true,
  "visa_check_note": "Found in tier_1_heavy_sponsors"
}
```

## Reference URLs (for manual verification)
- https://h1bdata.info
- https://www.myvisajobs.com
- https://h1bgrader.com
- https://h1bdatabase.com
- https://h1bmetrics.com
- https://lcadatacenter.dol.gov
