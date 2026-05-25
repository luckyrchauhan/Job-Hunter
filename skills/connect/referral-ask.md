# Skill: referral-ask

## Purpose
Draft a warm referral request when a shared connection or alumni background exists (warmth >= 2).

## When to Use
Lead found with `warmth >= 2`. Always try warm outreach before cold.

## Inputs
- `job` — job object from `jobs-scored.json`
- `lead` — contact from `leads.json`
- `my_background` — from `data/my-resume.md`

## Warm Connection Hooks (check in order)
1. **BU MBA alumni** — "Fellow BU Questrom alum here"
2. **Supply chain / maritime background** — shared Anglo-Eastern / shipping domain
3. **SAP / enterprise platform** — shared tech domain
4. **AI/LLM product work** — shared space, mention knowledge platform
5. **Mutual LinkedIn connection** — cite the person by name

## Message Template

```
Subject: [Company] [Role] — Fellow [shared hook]

Hi [First Name],

[Opening hook — 1 sentence: shared connection or context]

I came across the [Role Title] role at [Company] and it's a strong match — [1-2 specifics from JD that match my background, e.g., "enterprise platform scale" or "AI product experience"].

Quick background: I'm a PM with 11 years of experience, most recently building [most relevant recent project]. I've [1 key credential matching JD].

Would you be open to a 15-minute chat, or if it's easier, just pointing me to the right person on the team?

[Optional: "Happy to share my resume / LinkedIn."]

Thanks,
Your Name
your.email@example.com | linkedin.com/in/your-profile
```

## Tone Rules
- Max 150 words total
- Specific, not generic — name something real from their company or JD
- One clear ask only (chat OR referral, not both)
- No "I hope this message finds you well"
- No desperation — peer tone, not supplicant

## Output
- Write to `outputs/outreach/[company]-[role-slug]-referral-[date].md`
- Flag `outreach_type: "referral"` in leads entry

## Example Hook Lines by Warmth Source
- BU: "I saw we're both Questrom alums — wanted to reach out directly."
- Maritime: "Your time at [shipping company] caught my eye — I spent 7 years at Anglo-Eastern managing fleet operations."
- AI/LLM: "Your team's work on [product] overlaps a lot with the LLM knowledge platform I built at GlobalLogic."
