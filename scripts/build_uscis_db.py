#!/usr/bin/env python3
"""
Download USCIS H-1B Employer Data Hub CSVs and build a local lookup DB.
Aggregates all legal entities by normalized company name.

Run: python scripts/build_uscis_db.py
Output: data/uscis-h1b-db.json
Schedule: weekly (or run manually to refresh)
"""

import csv
import io
import json
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
OUT_FILE = BASE_DIR / "data" / "uscis-h1b-db.json"

USCIS_BASE = "https://www.uscis.gov/sites/default/files/document/data"
# Most recent 3 fiscal years available
YEARS = [2023, 2022, 2021]

LEGAL_SUFFIXES = re.compile(
    r"\b(llc|inc|corp|corporation|ltd|limited|lp|llp|co|company|"
    r"incorporated|solutions|technologies|services|group|holdings|"
    r"enterprises|associates|partners|international|global|us|usa)\b\.?$",
    re.I,
)


def normalize(name: str) -> str:
    n = name.lower().strip()
    n = re.sub(r"[,\.]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    # strip trailing legal suffixes iteratively
    for _ in range(4):
        prev = n
        n = LEGAL_SUFFIXES.sub("", n).strip()
        if n == prev:
            break
    return n.strip()


def fetch_year(year: int) -> list[dict]:
    url = f"{USCIS_BASE}/h1b_datahubexport-{year}.csv"
    print(f"  Fetching USCIS {year}...", end=" ", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode("utf-8", errors="ignore")
        rows = list(csv.DictReader(io.StringIO(raw)))
        print(f"{len(rows):,} rows")
        return rows
    except Exception as e:
        print(f"FAILED: {e}")
        return []


def build_db() -> dict:
    # norm_name -> {years: {year: approvals}, total_approvals, total_denials, entities: [original names]}
    db: dict[str, dict] = defaultdict(lambda: {
        "total_approvals": 0,
        "total_denials": 0,
        "years": {},
        "entities": [],
    })

    for year in YEARS:
        rows = fetch_year(year)
        for row in rows:
            raw_name = (row.get("Employer") or "").strip()
            if not raw_name:
                continue
            norm = normalize(raw_name)
            if not norm:
                continue

            ia  = int(row.get("Initial Approval")    or 0)
            id_ = int(row.get("Initial Denial")      or 0)
            ca  = int(row.get("Continuing Approval") or 0)
            cd  = int(row.get("Continuing Denial")   or 0)
            approvals = ia + ca
            denials   = id_ + cd

            entry = db[norm]
            entry["total_approvals"] += approvals
            entry["total_denials"]   += denials
            yr_key = str(year)
            entry["years"][yr_key] = entry["years"].get(yr_key, 0) + approvals
            if raw_name.lower() not in [e.lower() for e in entry["entities"]]:
                entry["entities"].append(raw_name)

    return dict(db)


def main():
    print("Building USCIS H-1B employer database...")
    db = build_db()

    # Quick stats
    total_employers = len(db)
    total_approvals = sum(v["total_approvals"] for v in db.values())
    print(f"  {total_employers:,} unique employers, {total_approvals:,} total approvals (2021-2023)")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(db, f, separators=(",", ":"))

    print(f"  Saved → {OUT_FILE}")

    # Test a few lookups
    print("\nSample lookups:")
    for company in ["google", "microsoft", "amazon", "stripe", "openai", "meta"]:
        entry = db.get(company)
        if entry:
            recent = max(entry["years"], key=lambda y: entry["years"][y]) if entry["years"] else "?"
            recent_count = entry["years"].get(recent, 0)
            total = entry["total_approvals"]
            print(f"  {company}: {total} total approvals | {recent_count} in {recent}")
        else:
            print(f"  {company}: not found (may be under subsidiary name)")


if __name__ == "__main__":
    main()
