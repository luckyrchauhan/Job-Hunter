# Skill: submit-checklist

## Purpose
Pre-apply QA gate. Verify all materials ready before Lucky hits Apply.

## When to Use
Final step before flagging a job as `ready_to_apply`.

## Inputs
- `job` — job object from `jobs-scored.json`
- `tailored_resume_path` — output from tailor-resume
- `cover_letter_path` — output from cover-letter
- `lead` — from `data/leads.json`
- `outreach_path` — output from referral-ask or cold-outreach

## Checklist

### Hard Blocks (FAIL = do not proceed)
- [ ] `score >= 6` — minimum fit threshold
- [ ] `visa_status != "no-sponsorship"` — never apply to non-sponsors
- [ ] Tailored resume file exists at `tailored_resume_path`
- [ ] Apply URL is valid (not expired / 404)
- [ ] Job posted <= 7 days ago (not stale)

### Soft Checks (WARN = flag but don't block)
- [ ] Cover letter exists at `cover_letter_path`
- [ ] Outreach message drafted (referral or cold)
- [ ] Lead found (recruiter or HM) — warn if missing
- [ ] Salary in JD >= $120k OR salary unknown (never apply if confirmed < $120k)
- [ ] Company not in `config/blocklist.json`

## Output Format

```
════════════════════════════════════════
SUBMIT CHECKLIST — [Company] / [Role]
════════════════════════════════════════
Score:           8/10  ✅
Visa:            confirmed  ✅
Resume:          outputs/resumes/stripe-pm-2026-05-25.md  ✅
Cover Letter:    outputs/cover-letters/stripe-pm-2026-05-25.md  ✅
Outreach:        outputs/outreach/stripe-pm-referral-2026-05-25.md  ✅
Lead:            Jane Doe (Recruiter)  ✅
Apply URL:       https://stripe.com/jobs/...  ✅
Posted:          1 day ago  ✅
Salary:          $160k–$200k  ✅

VERDICT: ✅ READY TO APPLY
════════════════════════════════════════
```

## On Pass
- Update job record: `"status": "ready_to_apply"`
- Slack alert (if urgency tier <= 3): "✅ Ready to apply: [Company] [Role] — Score: [X]"
- Lucky applies manually

## On Hard Fail
- Do NOT update status
- Print which check failed and why
- Suggest fix if possible (e.g., "salary < $120k — skip this role")
