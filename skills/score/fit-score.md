# Skill: fit-score — Score a Job Against Lucky's Resume

## Purpose
Score each raw job 0–10 vs Lucky Chauhan's resume. Higher = stronger match. Used by `scripts/score_jobs.py`.

## Inputs
- Job object (from `data/jobs-raw/*.json`)
- Resume: `data/my-resume.md`
- Weights: `config/score-weights.json`

## Scoring Dimensions

### Mandatory Hard Filters (fail = score 0, discard = true)
| Check | Rule |
|-------|------|
| Visa sponsorship | Company must be in Tier 1–3 of `config/target-companies.json` OR job description mentions "visa sponsorship" or "H1B" OR company cleared in visa-check skill. Tier 4 = flag for manual review, not auto-discard. |
| Salary | If salary_min present: must be ≥ $120,000. If no salary listed: do NOT discard — many remote jobs omit. |
| Posted recency | posted_date must be within 7 days of today. |
| Role relevance | Title must be a PM role (product manager, senior pm, apm, platform pm, ai pm, technical pm, vp product, director of product, associate pm, group pm). Not engineering, design, sales. |

### Weighted Score Components (0–10 scale)
| Dimension | Weight | Signal |
|-----------|--------|--------|
| AI/LLM keywords in JD | 2.0 | "LLM", "generative AI", "AI product", "machine learning", "RAG", "prompt", "foundation model", "agentic" |
| Role title match | 2.0 | Exact match to target roles > partial match |
| Skills overlap | 2.0 | JD keywords matching: SAP S/4HANA, supply chain, platform PM, enterprise, SQL, Python, agile, scrum, roadmap, A/B testing |
| Enterprise/platform domain | 1.5 | "enterprise", "platform", "B2B", "SaaS", "multi-tenant", "5000+ users", "global" |
| Supply chain domain | 1.5 | "supply chain", "logistics", "procurement", "manufacturing", "ERP", "warehouse", "inventory" |
| Experience level match | 1.5 | "senior" or "5+ years" or "7+ years" preferred. APM/associate ok for strong companies. |
| Remote / Indiana friendly | 1.0 | "remote", "fully remote", "work from anywhere" |
| Salary signal | 1.0 | Mentioned salary ≥ $150k = full point, $120–149k = 0.5, not listed = 0 (neutral) |

### Score Calculation
```
raw_score = sum(weight * signal_strength) for each dimension
normalized = (raw_score / max_possible_raw) * 10
final_score = round(normalized, 1)
```

### Score Bands
| Band | Score | Label | Action |
|------|-------|-------|--------|
| Strong | ≥ 8.0 | STRONG MATCH | Prioritize — apply within 24h |
| Good | ≥ 6.0 | GOOD MATCH | Apply this week |
| Weak | ≥ 4.0 | WEAK MATCH | Apply if time allows |
| Poor | < 4.0 | POOR MATCH | Skip |

## Output Fields (added to job object)
```json
{
  "score": 7.5,
  "score_band": "GOOD MATCH",
  "score_breakdown": {
    "ai_llm": 2.0,
    "title_match": 1.8,
    "skills_overlap": 1.2,
    "enterprise": 1.5,
    "supply_chain": 0.0,
    "experience": 1.0,
    "remote": 1.0,
    "salary": 0.5
  },
  "hard_filter_passed": true,
  "discard_reason": null,
  "visa_status": "tier_1",
  "sponsorship_confirmed": true
}
```

## Notes
- When description is empty (known Indeed bug): score on title + company only. Flag as `low_confidence: true`.
- When company is empty: attempt lookup from apply_url domain. Flag as `company_unknown: true`.
- Never auto-apply. Score is for Lucky's review only.
