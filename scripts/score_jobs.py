#!/usr/bin/env python3
"""
M3 — Score & Filter Jobs
Reads: data/jobs-raw/*.json
Writes: data/jobs-scored.json

Scoring: fit-score.md + visa-check.md + urgency-flag.md skills
No Claude API needed — pure rule-based scoring (fast, free, deterministic).
Claude API scoring planned for M3 enhancement once ANTHROPIC_API_KEY is set.
"""

import json
import os
import glob
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
RAW_DIR = BASE_DIR / "data" / "jobs-raw"
SCORED_FILE = BASE_DIR / "data" / "jobs-scored.json"
COMPANIES_FILE = BASE_DIR / "config" / "target-companies.json"

# ─── Load company tiers ───────────────────────────────────────────────────────

def load_company_tiers():
    with open(COMPANIES_FILE) as f:
        data = json.load(f)
    tiers = {}
    for tier_key in ["tier_1_heavy_sponsors", "tier_2_consistent_sponsors",
                     "tier_3_startup_sponsors", "tier_4_verify_first"]:
        for company in data.get(tier_key, {}).get("companies", []):
            tiers[normalize_company(company)] = tier_key
    return tiers

def normalize_company(name: str) -> str:
    if not name:
        return ""
    name = name.lower()
    for suffix in [" inc.", " inc", " llc", " corp.", " corp", " ltd.", " ltd",
                   " technologies", " technology", " solutions", " software"]:
        name = name.replace(suffix, "")
    name = name.replace("&", "and").strip()
    return name

COMPANY_TIERS = load_company_tiers()

# ─── Visa Check ───────────────────────────────────────────────────────────────

NO_SPONSOR_PHRASES = [
    "must be authorized to work",
    "no sponsorship",
    "us citizen or permanent resident only",
    "security clearance required",
    "must be a us citizen",
    "authorized to work in the us without sponsorship",
]

SPONSOR_PHRASES = [
    "visa sponsorship available",
    "will sponsor h1b",
    "h1b transfer",
    "opt/cpt accepted",
    "sponsor work visa",
    "h-1b",
]

def check_visa(company: str, description: str) -> dict:
    norm = normalize_company(company)
    desc_lower = (description or "").lower()

    # Exact match
    if norm and norm in COMPANY_TIERS:
        tier = COMPANY_TIERS[norm]
        return {
            "visa_status": tier.replace("_heavy_sponsors", "_1")
                              .replace("_consistent_sponsors", "_2")
                              .replace("_startup_sponsors", "_3")
                              .replace("_verify_first", "_4"),
            "visa_status_raw": tier,
            "sponsorship_confirmed": tier in ["tier_1_heavy_sponsors", "tier_2_consistent_sponsors"],
            "visa_check_note": f"Found in {tier}",
        }

    # Fuzzy match
    for tier_company, tier in COMPANY_TIERS.items():
        if tier_company and norm and (tier_company in norm or norm in tier_company):
            return {
                "visa_status": tier,
                "sponsorship_confirmed": tier in ["tier_1_heavy_sponsors", "tier_2_consistent_sponsors"],
                "visa_check_note": f"Fuzzy match to {tier_company} in {tier}",
            }

    # Negative signals in JD
    for phrase in NO_SPONSOR_PHRASES:
        if phrase in desc_lower:
            return {
                "visa_status": "no_sponsorship",
                "sponsorship_confirmed": False,
                "visa_check_note": f"No sponsorship signal: '{phrase}'",
                "discard": True,
                "discard_reason": "no_sponsorship",
            }

    # Positive signals in JD
    for phrase in SPONSOR_PHRASES:
        if phrase in desc_lower:
            return {
                "visa_status": "jd_confirmed",
                "sponsorship_confirmed": True,
                "visa_check_note": f"JD mentions: '{phrase}'",
            }

    return {
        "visa_status": "unknown",
        "sponsorship_confirmed": False,
        "visa_check_note": "Company not in tiers, no JD signal — manual verify",
    }

# ─── Fit Score ────────────────────────────────────────────────────────────────

PM_TITLES = [
    "product manager",
    "ai product manager",
]

# Titles that look like PM but are wrong level — hard filtered out
EXCLUDED_TITLES = [
    "senior product manager", "senior pm", "sr product manager", "sr. product manager",
    "principal product manager", "principal pm",
    "director of product", "director, product", "director of pm",
    "vp of product", "vp product", "vice president of product",
    "head of product",
    "group product manager", "group pm",
    "staff product manager",
    "lead product manager",
    "technical program manager",
    "engineering manager",
]

NON_PM_DISCARD = [
    "software engineer", "data engineer", "data scientist", "designer",
    "sales", "account executive", "recruiter", "devops", "sre", "qa",
    "marketing", "finance", "legal", "chief operating officer", "coo",
    "chief executive", "cfo", "general counsel",
]

AI_KEYWORDS = [
    "llm", "generative ai", "gen ai", "ai product", "machine learning",
    "artificial intelligence", "rag", "prompt engineering", "foundation model",
    "agentic", "chatgpt", "gpt", "claude", "large language model",
    "nlp", "vector", "embedding", "fine-tuning",
]

SKILLS_KEYWORDS = [
    "sap", "s/4hana", "supply chain", "platform", "enterprise", "b2b",
    "sql", "python", "agile", "scrum", "roadmap", "a/b test", "okr",
    "analytics", "data-driven", "stakeholder", "cross-functional",
]

ENTERPRISE_KEYWORDS = [
    "enterprise", "platform", "b2b", "saas", "multi-tenant", "global",
    "large scale", "5000", "10000",
]

SUPPLY_CHAIN_KEYWORDS = [
    "supply chain", "logistics", "procurement", "manufacturing", "erp",
    "warehouse", "inventory", "fulfillment", "operations",
]

SENIOR_KEYWORDS = [
    "senior", "sr.", "sr ", "lead", "principal", "staff", "director",
    "5+ years", "6+ years", "7+ years", "8+ years",
]

REMOTE_KEYWORDS = [
    "remote", "fully remote", "work from anywhere", "distributed",
    "work from home", "wfh",
]


def score_keywords(text: str, keywords: list) -> float:
    """Return 0–1 based on keyword density."""
    if not text:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw in text_lower)
    return min(1.0, hits / max(1, len(keywords) * 0.3))


def score_job(job: dict) -> dict:
    title = (job.get("title") or "").lower()
    company = job.get("company") or ""
    description = (job.get("description") or "").lower()
    location = (job.get("location") or "").lower()
    salary_min = job.get("salary_min")
    posted_date_str = job.get("posted_date") or job.get("scraped_at", "")[:10]

    combined_text = f"{title} {description}"
    low_confidence = not description  # empty description

    # ── Hard filter: role relevance ──
    title_is_pm = any(t in title for t in PM_TITLES)
    title_is_non_pm = any(t in title for t in NON_PM_DISCARD)
    title_is_excluded = any(t in title for t in EXCLUDED_TITLES)

    # Exclude wrong-level titles (Senior PM, Director, VP, etc.)
    if title_is_excluded:
        return {**job,
                "score": 0.0, "score_band": "DISCARD",
                "discard": True, "discard_reason": "wrong_level_title",
                "hard_filter_passed": False}

    if title_is_non_pm and not title_is_pm:
        return {**job,
                "score": 0.0, "score_band": "DISCARD",
                "discard": True, "discard_reason": "not_pm_role",
                "hard_filter_passed": False}

    # ── Hard filter: recency ──
    try:
        posted = datetime.strptime(posted_date_str, "%Y-%m-%d").date()
        days_old = (datetime.now().date() - posted).days
    except Exception:
        days_old = 0

    if days_old > 14:
        return {**job,
                "score": 0.0, "score_band": "EXPIRED",
                "discard": True, "discard_reason": "expired",
                "hard_filter_passed": False}

    # ── Hard filter: salary ──
    if salary_min and salary_min < 120000:
        return {**job,
                "score": 0.0, "score_band": "DISCARD",
                "discard": True, "discard_reason": f"salary_below_min_{salary_min}",
                "hard_filter_passed": False}

    # ── Visa check ──
    visa = check_visa(company, description)
    if visa.get("discard"):
        return {**job, **visa,
                "score": 0.0, "score_band": "DISCARD",
                "hard_filter_passed": False}

    # ── Fit scoring ──
    breakdown = {}

    # AI/LLM (weight 2.0)
    breakdown["ai_llm"] = round(score_keywords(combined_text, AI_KEYWORDS) * 2.0, 2)

    # Title match (weight 2.0)
    if any(t in title for t in ["senior", "principal", "staff", "lead", "director", "vp"]):
        title_score = 2.0
    elif title_is_pm:
        title_score = 1.6
    else:
        title_score = 0.8
    breakdown["title_match"] = title_score

    # Skills overlap (weight 2.0)
    breakdown["skills_overlap"] = round(score_keywords(combined_text, SKILLS_KEYWORDS) * 2.0, 2)

    # Enterprise (weight 1.5)
    breakdown["enterprise"] = round(score_keywords(combined_text, ENTERPRISE_KEYWORDS) * 1.5, 2)

    # Supply chain (weight 1.5)
    breakdown["supply_chain"] = round(score_keywords(combined_text, SUPPLY_CHAIN_KEYWORDS) * 1.5, 2)

    # Experience level (weight 1.5)
    breakdown["experience"] = round(score_keywords(combined_text, SENIOR_KEYWORDS) * 1.5, 2)

    # Remote (weight 1.0)
    remote_hit = job.get("remote") or any(r in location for r in REMOTE_KEYWORDS) or any(r in combined_text for r in REMOTE_KEYWORDS)
    breakdown["remote"] = 1.0 if remote_hit else 0.0

    # Salary signal (weight 1.0)
    salary_max = job.get("salary_max")
    if salary_max and salary_max >= 150000:
        breakdown["salary"] = 1.0
    elif salary_min and salary_min >= 120000:
        breakdown["salary"] = 0.5
    else:
        breakdown["salary"] = 0.0

    # ── Normalize to 0–10 ──
    max_possible = 2.0 + 2.0 + 2.0 + 1.5 + 1.5 + 1.5 + 1.0 + 1.0  # = 12.5
    raw = sum(breakdown.values())
    score = round((raw / max_possible) * 10, 1)

    if score >= 8.0:
        band = "STRONG MATCH"
    elif score >= 6.0:
        band = "GOOD MATCH"
    elif score >= 4.0:
        band = "WEAK MATCH"
    else:
        band = "POOR MATCH"

    # ── Urgency ──
    urgency = compute_urgency(score, days_old, description)

    # ── Priority Score (cumulative apply rank, normalized 0–10) ──
    priority = compute_priority_score(
        fit_score=score,
        salary_min=salary_min,
        salary_max=salary_max,
        visa_result=visa,
        description=description,
        days_old=days_old,
        remote=remote_hit,
        location=location,
    )

    return {
        **job,
        **visa,
        "score": score,
        "score_band": band,
        "score_breakdown": breakdown,
        "hard_filter_passed": True,
        "discard": False,
        "discard_reason": None,
        "low_confidence": low_confidence,
        "company_unknown": not company,
        **urgency,
        **priority,
    }


# ─── Priority Score ──────────────────────────────────────────────────────────

H1B_EXPLICIT_PHRASES = [
    "h1b sponsor", "h-1b sponsor", "will sponsor h1b", "h1b transfer",
    "visa sponsorship provided", "sponsoring h1b", "h1b visa sponsor",
    "sponsor h-1b", "h1b welcome",
]

PREVIOUS_COMPANIES = [
    "accenture", "tata", "infosys", "wipro", "cognizant", "hcl",
    # add more from your resume as needed
]

def compute_priority_score(
    fit_score: float,
    salary_min,
    salary_max,
    visa_result: dict,
    description: str,
    days_old: int,
    remote: bool,
    location: str,
) -> dict:
    """
    Cumulative apply-priority score normalized to 0–10.
    Weights (raw max = 22):
      fit_score (0–10)           → up to 10 pts (mapped directly)
      H1B explicitly in JD       → +4 pts  (highest single bonus)
      H1B likely (tier 1/2)      → +1 pt
      Salary ≥ $150k             → +2 pts
      Salary $120–150k           → +1 pt
      Posted < 2hrs              → +2 pts
      Posted < 24hrs             → +1 pt
      Remote                     → +1 pt
      Boston / Indiana location  → +0.5 pt
    Connections bonuses added later when CSV loaded:
      Indian-origin in USA       → +3 pts
      BU alum / prev company     → +2 pts
      Any connection             → +1 pt
    """
    desc_lower = (description or "").lower()
    raw = fit_score  # base: fit score already 0–10

    # H1B — highest weight
    h1b_explicit = any(p in desc_lower for p in H1B_EXPLICIT_PHRASES)
    if h1b_explicit:
        raw += 4
        h1b_bonus = "explicit_+4"
    elif visa_result.get("visa_status_raw") in ["tier_1_heavy_sponsors", "tier_2_consistent_sponsors"]:
        raw += 1
        h1b_bonus = "likely_+1"
    else:
        h1b_bonus = "none"

    # Salary
    salary_bonus = 0
    if salary_max and salary_max >= 150000:
        salary_bonus = 2
    elif salary_min and salary_min >= 120000:
        salary_bonus = 1
    raw += salary_bonus

    # Recency
    recency_bonus = 0
    hours_old = days_old * 24
    if hours_old < 2:
        recency_bonus = 2
    elif hours_old < 24:
        recency_bonus = 1
    raw += recency_bonus

    # Remote
    remote_bonus = 1 if remote else 0
    raw += remote_bonus

    # Location
    location_bonus = 0
    if any(loc in location for loc in ["boston", "indiana", "indianapolis", "remote"]):
        location_bonus = 0.5
    raw += location_bonus

    # Normalize: max without connections = 10+4+2+2+1+0.5 = 19.5
    # Reserve headroom for connections (+3 max) → max_possible = 22.5
    MAX_POSSIBLE = 22.5
    priority = round(min((raw / MAX_POSSIBLE) * 10, 10.0), 1)

    if priority >= 8.0:
        priority_band = "🔥 Apply Now"
    elif priority >= 6.0:
        priority_band = "⚡ Apply Soon"
    elif priority >= 4.0:
        priority_band = "👀 Consider"
    else:
        priority_band = "📋 Low Priority"

    return {
        "priority_score": priority,
        "priority_band": priority_band,
        "priority_breakdown": {
            "fit_score": fit_score,
            "h1b_bonus": h1b_bonus,
            "salary_bonus": salary_bonus,
            "recency_bonus": recency_bonus,
            "remote_bonus": remote_bonus,
            "location_bonus": location_bonus,
            "connection_bonus": 0,  # filled when connections CSV loaded
        },
    }


# ─── Urgency Flag ─────────────────────────────────────────────────────────────

CLOSING_SIGNALS = ["apply by", "position closes", "rolling basis", "until filled", "deadline"]

def compute_urgency(score: float, days_old: int, description: str) -> dict:
    desc_lower = (description or "").lower()
    closing = any(s in desc_lower for s in CLOSING_SIGNALS)

    hours_old = days_old * 24  # approximate

    if hours_old < 6 and score >= 8:
        tier, label, alert = 1, "APPLY NOW", True
    elif hours_old < 24 and score >= 8:
        tier, label, alert = 2, "APPLY NOW", True
    elif closing or (hours_old < 24 and score >= 6):
        tier, label, alert = 4, "<15 HOURS", True
    elif days_old <= 3 and score >= 6:
        tier, label, alert = 5, "THIS WEEK", False
    elif days_old <= 7 and score >= 4:
        tier, label, alert = 6, "THIS WEEK", False
    elif days_old <= 14:
        tier, label, alert = 7, "LOW PRIORITY", False
    else:
        tier, label, alert = 8, "EXPIRED", False

    if closing and tier > 3:
        tier = max(1, tier - 1)
        alert = True

    return {
        "urgency_tier": tier,
        "urgency_label": label,
        "days_since_posted": days_old,
        "closing_signal": closing,
        "alert_now": alert,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def _dedup_key(job: dict) -> str:
    """
    Cross-source dedup key: normalized (title + company + location).
    Same job posted on LinkedIn + Indeed → same key → keep first seen (higher-confidence source).
    Falls back to source-scoped ID if title/company both empty.
    """
    import hashlib
    title = re.sub(r'\s+', ' ', (job.get("title") or "").lower().strip())
    company = re.sub(r'\s+', ' ', (job.get("company") or "").lower().strip())
    # Normalize location: "remote, usa" / "remote" / "united states (remote)" → "remote"
    loc = (job.get("location") or "").lower()
    location = "remote" if "remote" in loc else re.sub(r'\s+', ' ', loc.strip())

    if title and company:
        raw = f"{title}|{company}|{location}"
        return hashlib.md5(raw.encode()).hexdigest()
    # No company yet (JS-render issue) — fall back to source-scoped ID
    return job.get("id", f"unknown-{title}")


def load_all_raw_jobs():
    all_jobs = []
    seen_ids = set()      # source-level dedup (same file repeated)
    seen_dedup = set()    # cross-source dedup (same job on multiple boards)
    dupes = 0

    for fpath in sorted(glob.glob(str(RAW_DIR / "*.json"))):
        try:
            with open(fpath) as f:
                jobs = json.load(f)
            for job in jobs:
                jid = job.get("id") or f"{job.get('source','?')}-{job.get('apply_url','')}"
                if jid in seen_ids:
                    continue
                seen_ids.add(jid)

                dkey = _dedup_key(job)
                if dkey in seen_dedup:
                    dupes += 1
                    continue
                seen_dedup.add(dkey)
                all_jobs.append(job)
        except Exception as e:
            print(f"  ⚠ Error reading {fpath}: {e}")

    if dupes:
        print(f"  🔁 Cross-source dedup removed {dupes} duplicate job(s)")
    return all_jobs


def main():
    print("=" * 60)
    print("M3 — Job Scorer")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    jobs = load_all_raw_jobs()
    print(f"\n📥 Loaded {len(jobs)} raw jobs from {RAW_DIR}")

    scored = []
    stats = {"strong": 0, "good": 0, "weak": 0, "poor": 0, "discard": 0}

    for job in jobs:
        result = score_job(job)
        scored.append(result)

        band = result.get("score_band", "")
        if "STRONG" in band:
            stats["strong"] += 1
        elif "GOOD" in band:
            stats["good"] += 1
        elif "WEAK" in band:
            stats["weak"] += 1
        elif "POOR" in band:
            stats["poor"] += 1
        else:
            stats["discard"] += 1

    # Sort: Boston/MA first, then remote, then other US — within each group by score desc
    def location_priority(j):
        loc = (j.get("location") or "").lower()
        if any(k in loc for k in ["boston", "cambridge, ma", "massachusetts", ", ma", "(ma)"]):
            return 0  # Boston/MA — top priority
        if any(k in loc for k in ["remote", "anywhere", "united states", "usa", "us only"]):
            return 1  # Remote US
        return 2      # Other US cities

    scored.sort(key=lambda j: (location_priority(j), -j.get("score", 0)))

    # Save
    with open(SCORED_FILE, "w") as f:
        json.dump(scored, f, indent=2, default=str)

    print(f"\n📊 Scoring Results:")
    print(f"  🟢 STRONG (≥8.0): {stats['strong']}")
    print(f"  🔵 GOOD   (≥6.0): {stats['good']}")
    print(f"  🟡 WEAK   (≥4.0): {stats['weak']}")
    print(f"  ⚪ POOR   (<4.0): {stats['poor']}")
    print(f"  ❌ DISCARD:       {stats['discard']}")
    print(f"\n✅ Saved {len(scored)} scored jobs → {SCORED_FILE}")

    # Print top 5
    actionable = [j for j in scored if not j.get("discard") and j.get("score", 0) >= 6]
    if actionable:
        print(f"\n🎯 Top {min(5, len(actionable))} Matches:")
        for j in actionable[:5]:
            visa_icon = "✅" if j.get("sponsorship_confirmed") else "⚠️"
            print(f"  [{j['score']}] {j.get('score_band','?')} | {visa_icon} {j.get('company','Unknown')} — {j.get('title','?')}")
            print(f"       {j.get('urgency_label','?')} | {j.get('apply_url','')[:60]}")
    else:
        print("\n⚠ No GOOD/STRONG matches found in current raw jobs.")
        print("  (Expected — Indeed has empty descriptions, boosting score will require fixing M2 scrapers)")


if __name__ == "__main__":
    main()
