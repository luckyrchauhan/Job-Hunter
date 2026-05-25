# Skill: cold-outreach

## Purpose
Draft cold outreach when no warm connection exists (warmth = 1) or no lead found.

## When to Use
Lead warmth = 1, OR leads_not_found = true. Fallback after referral-ask.

## Inputs
- `job` — job object from `jobs-scored.json`
- `lead` — contact (may be null if no lead found)
- `target` — "recruiter" | "hiring_manager" (prefer recruiter for cold)

## Cold Message Template (LinkedIn message / email)

```
Subject: [Role Title] @ [Company] — PM with [Most Relevant Credential]

Hi [First Name],

I'm applying for the [Role Title] position and wanted to reach out directly.

I'm a PM with 11 years of experience — most relevant here: [1 specific thing from JD mapped to my background, e.g., "led AI product from 0→1 at GlobalLogic" or "owned $20M enterprise platform at Katbotz"].

[Company] is specifically on my list because [1 genuine reason — product direction, company mission, or specific team work].

I'd appreciate a 15-minute conversation if you have time, or any guidance on the process.

Thanks,
Lucky Chauhan
lucky.raajc@gmail.com | linkedin.com/in/luckychauhan
```

## Tone Rules
- Max 120 words
- One specific credential, not a list
- One genuine reason for targeting this company — not flattery
- Single ask: conversation OR process guidance
- No "I've always dreamed of working at..."

## No-Lead Fallback
If `leads_not_found = true`:
- Draft message anyway addressed to "Hiring Team"
- Save to `outputs/outreach/[company]-[role-slug]-cold-[date].md`
- Note in output: `"no_lead_found — address to team or find via LinkedIn manually"`

## Output
- Write to `outputs/outreach/[company]-[role-slug]-cold-[date].md`
- Flag `outreach_type: "cold"` in leads entry
