#!/usr/bin/env python3
"""
Launchboard UK graduate / entry-level business job collector.
The scoring model is tailored to a 2027 Business Management graduate profile
with interests in consulting, strategy, commercial work, financial services,
client-facing roles and business development.
"""
import json, os, re, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

APP_ID = os.environ["ADZUNA_APP_ID"]
APP_KEY = os.environ["ADZUNA_APP_KEY"]
OUT = Path(__file__).with_name("jobs.json")

# Keep this at 12 queries: 6 runs/day ~= 2,160 calls/month, inside the
# standard 2,500/month Adzuna allowance.
QUERIES = [
    "graduate strategy",
    "graduate consultant",
    "graduate business analyst",
    "graduate commercial",
    "graduate operations",
    "graduate management",
    "graduate business development",
    "graduate sales",
    "revenue operations analyst",
    "graduate recruitment consultant",
    "graduate client services",
    "graduate project management",
]

EARLY = [
    "graduate", "entry level", "entry-level", "junior", "trainee",
    "early career", "early-career", "no experience", "school leaver"
]

TITLE_EXCLUDE = [
    "internship", "summer intern", "placement", "apprentice",
    "software engineer", "software developer", "data engineer",
    "data scientist", "machine learning", "quant developer",
    "quant researcher", "quantitative researcher", "algorithmic trader",
    "doctor", "nurse", "solicitor", "lawyer", "architect"
]

ROLE_WEIGHTS = [
    ("strategy", 20),
    ("management consulting", 20),
    ("strategy consulting", 22),
    ("consultant", 17),
    ("consulting", 17),
    ("business analyst", 18),
    ("revenue operations", 19),
    ("commercial analyst", 17),
    ("operations analyst", 15),
    ("market analysis", 14),
    ("market research", 12),
    ("business development", 15),
    ("sales development", 12),
    ("account executive", 10),
    ("client service", 15),
    ("client services", 15),
    ("account management", 11),
    ("customer success", 9),
    ("executive search", 13),
    ("recruitment consultant", 12),
    ("commercial", 13),
    ("operations", 10),
    ("business operations", 14),
    ("management graduate", 14),
    ("graduate management", 14),
    ("project management", 9),
    ("change management", 10),
    ("business transformation", 13),
    ("transformation", 9),
    ("partnerships", 9),
    ("growth", 7),
    ("procurement", 7),
    ("supply chain", 6),
    ("financial services", 10),
    ("financial markets", 11),
    ("fintech", 11),
    ("payments", 9),
]

# Skills evidenced in the CV. These are light bonuses; role family and
# eligibility remain more important than generic soft-skill wording.
PROFILE_WEIGHTS = [
    ("relationship", 4),
    ("client", 4),
    ("customer", 3),
    ("communication", 3),
    ("stakeholder", 3),
    ("leadership", 5),
    ("teamwork", 2),
    ("team environment", 2),
    ("problem solving", 3),
    ("problem-solving", 3),
    ("resilience", 3),
    ("adaptability", 3),
    ("fast-paced", 3),
    ("analysis", 3),
    ("research", 3),
    ("commercial awareness", 4),
    ("decision-making", 3),
]

CATS = [
    ("Strategy & Consulting", ["strategy", "consultant", "consulting", "advisory"]),
    ("Business Analysis & Insights", ["business analyst", "market analysis", "market research", "insights analyst"]),
    ("Revenue & Commercial Operations", ["revenue operations", "revops", "commercial analyst", "sales operations"]),
    ("Business Development & Sales", ["business development", "sales development", "account executive", "growth executive"]),
    ("Client Services & Account Management", ["client service", "client services", "account management", "customer success"]),
    ("Recruitment & Executive Search", ["recruitment", "executive search", "talent consultant"]),
    ("Operations & Management", ["operations", "management graduate", "graduate management", "management trainee"]),
    ("Project & Change", ["project management", "project coordinator", "change management", "transformation"]),
    ("Marketing & Growth", ["marketing", "growth"]),
    ("Procurement & Supply Chain", ["procurement", "supply chain", "logistics"]),
    ("Financial Services", ["financial services", "financial markets", "fintech", "payments", "banking"]),
    ("Commercial", ["commercial", "business graduate"]),
]

def fetch(query, page=1):
    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "results_per_page": 50,
        "what": query,
        "sort_by": "date",
        "content-type": "application/json",
    }
    url = f"https://api.adzuna.com/v1/api/jobs/gb/search/{page}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Launchboard/3.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("results", [])

def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()

def blob(title, desc):
    return (clean(title) + " " + clean(desc)).lower()

def hard_excluded(title):
    t = clean(title).lower()
    if any(x in t for x in TITLE_EXCLUDE):
        return True
    if any(x in t for x in ["director", "head of", "vice president", "principal"]):
        return True
    if re.search(r"\bsenior\b", t) and not any(x in t for x in EARLY):
        return True
    if re.search(r"\bmanager\b", t) and not any(x in t for x in ["graduate manager", "management graduate", "management trainee"]):
        return True
    return False

def relevant(title, desc):
    if hard_excluded(title):
        return False
    h = blob(title, desc)
    desired = [
        "strategy", "consult", "business analyst", "commercial", "operations",
        "business development", "sales development", "revenue operations",
        "client service", "account management", "customer success",
        "recruitment", "executive search", "project management",
        "management graduate", "graduate management", "partnership",
        "procurement", "supply chain", "financial services", "financial markets",
        "fintech", "payments", "market analysis", "market research",
        "business transformation", "change management"
    ]
    return any(x in h for x in desired)

def category(text):
    t = text.lower()
    for name, keys in CATS:
        if any(k in t for k in keys):
            return name
    return "Commercial"

def sector(text):
    t = text.lower()
    if any(k in t for k in ["fintech", "financial services", "financial markets", "banking", "payments", "investment"]):
        return "Financial Services / FinTech"
    if any(k in t for k in ["recruitment", "executive search", "staffing"]):
        return "Recruitment / Executive Search"
    if any(k in t for k in ["consulting", "consultant", "advisory"]):
        return "Consulting / Advisory"
    if any(k in t for k in ["property", "real estate", "surveying"]):
        return "Real Estate / Property"
    if any(k in t for k in ["software", "saas", "technology", "tech company"]):
        return "Technology / SaaS"
    if any(k in t for k in ["retail", "consumer", "fmcg"]):
        return "Consumer / Retail"
    return "Business / Commercial"

def experience_years(text):
    h = text.lower()
    years = []
    for m in re.finditer(r"\b([1-9])\+?\s*(?:-|to\s*)?years?\b", h):
        try:
            years.append(int(m.group(1)))
        except Exception:
            pass
    word_map = {"one":1, "two":2, "three":3, "four":4, "five":5}
    for w, n in word_map.items():
        if re.search(rf"\b{w}\+?\s+years?\b", h):
            years.append(n)
    return max(years) if years else 0

def eligibility(title, desc):
    if hard_excluded(title):
        return 0
    h = blob(title, desc)
    yrs = experience_years(h)
    if yrs >= 3:
        return 20
    if yrs == 2:
        return 40
    if yrs == 1:
        return 65
    if any(x in h for x in EARLY) or "2027" in h:
        return 100
    if any(x in title.lower() for x in ["associate", "analyst", "executive", "coordinator"]):
        return 86
    return 75

def fit_reasons(title, desc):
    h = blob(title, desc)
    reasons = []
    if any(x in h for x in ["strategy", "consulting", "consultant", "business transformation"]):
        reasons.append("Consulting / strategy aligned")
    if any(x in h for x in ["business development", "sales development", "commercial", "revenue operations"]):
        reasons.append("Commercial / growth aligned")
    if any(x in h for x in ["financial services", "financial markets", "fintech", "payments", "banking"]):
        reasons.append("Financial-services exposure")
    if any(x in h for x in ["client", "customer", "relationship", "stakeholder"]):
        reasons.append("Client & relationship heavy")
    if any(x in h for x in ["analysis", "research", "insight", "market"]):
        reasons.append("Analytical / market focus")
    if any(x in h for x in ["leadership", "teamwork", "collaborat", "resilience", "adaptability"]):
        reasons.append("Matches leadership / teamwork strengths")
    if any(x in h for x in ["recruitment", "executive search", "candidate sourcing"]):
        reasons.append("Builds on recruitment experience")
    if "2027" in h:
        reasons.append("2027 intake")
    if any(x in h for x in ["graduate", "entry level", "entry-level", "no experience"]):
        reasons.append("Early-career friendly")
    return reasons

def score_job(title, desc):
    h = blob(title, desc)
    if hard_excluded(title) or not relevant(title, desc):
        return 0
    score = 34

    if "2027" in h:
        score += 13
    if "graduate" in h:
        score += 19
    if "entry level" in h or "entry-level" in h:
        score += 17
    if "no experience" in h:
        score += 13
    if "trainee" in h:
        score += 10
    if "junior" in h:
        score += 8

    for k, v in ROLE_WEIGHTS:
        if k in h:
            score += v
    for k, v in PROFILE_WEIGHTS:
        if k in h:
            score += v

    yrs = experience_years(h)
    if yrs >= 3:
        score -= 50
    elif yrs == 2:
        score -= 32
    elif yrs == 1:
        score -= 15

    # Lower priority than the roles evidenced by the CV, but still potentially useful.
    if any(x in h for x in ["audit", "tax graduate", "accounting graduate", "actuarial"]):
        score -= 15
    if any(x in h for x in ["engineering degree", "computer science degree", "stem degree required"]):
        score -= 22

    return max(0, min(99, score))

def salary_text(x):
    lo = x.get("salary_min")
    hi = x.get("salary_max")
    if lo and hi:
        lo = int(round(lo)); hi = int(round(hi))
        if lo == hi:
            return f"£{lo:,}", hi
        return f"£{lo:,}–£{hi:,}", hi
    if lo:
        lo = int(round(lo)); return f"From £{lo:,}", lo
    if hi:
        hi = int(round(hi)); return f"Up to £{hi:,}", hi
    return "Not specified", 0

def age_days(created):
    if not created:
        return 999
    try:
        dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        return max(0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).days)
    except Exception:
        return 999

def make_job(x):
    title = clean(x.get("title"))
    desc = clean(x.get("description"))
    company = clean((x.get("company") or {}).get("display_name")) or "Company"
    loc = clean((x.get("location") or {}).get("display_name")) or "United Kingdom"
    sal, salmax = salary_text(x)
    h = blob(title, desc)
    s = score_job(title, desc)
    e = eligibility(title, desc)
    created = x.get("created") or ""
    age = age_days(created)
    ident = str(x.get("id") or abs(hash((title, company, loc))))
    reasons = fit_reasons(title, desc)
    if salmax:
        reasons.append("Salary disclosed")
    reasons = list(dict.fromkeys(reasons))

    return {
        "id": "adz-" + ident,
        "company": company,
        "initials": "".join(w[0] for w in company.split()[:2]).upper(),
        "title": title,
        "category": category(title + " " + desc),
        "location": loc,
        "workplace": "Check listing",
        "salary": sal,
        "salaryMax": salmax,
        "level": "Graduate" if "graduate" in h else "Entry Level",
        "posted": created[:10] if created else "Recent",
        "age": age,
        "new": age <= 7,
        "score": s,
        "eligibility": e,
        "priority": "A+" if s >= 94 else "A" if s >= 85 else "B" if s >= 70 else "C",
        "sector": sector(title + " " + desc),
        "url": x.get("redirect_url") or "https://www.adzuna.co.uk/",
        "reason": " · ".join(reasons[:4]) or "Potential business / commercial match",
        "tags": [category(title + " " + desc), sector(title + " " + desc), "UK", "Graduate / Entry Level"],
        "summary": desc[:500] + ("…" if len(desc) > 500 else ""),
        "fit": reasons[:6] or ["Potential business / commercial match"],
        "caution": "Confirm exact start date, degree criteria and experience requirements on the original listing."
    }

def main():
    found = {}
    for q in QUERIES:
        try:
            for x in fetch(q, 1):
                j = make_job(x)
                if j["eligibility"] >= 60 and j["score"] >= 60 and relevant(j["title"], x.get("description") or ""):
                    key = (j["company"].lower(), j["title"].lower(), j["location"].lower())
                    if key not in found or j["score"] > found[key]["score"]:
                        found[key] = j
        except Exception as exc:
            print("query failed:", q, exc)

    jobs = sorted(found.values(), key=lambda j: (-j["score"], j["age"], j["company"]))[:300]
    if not jobs:
        print("No jobs returned; keeping the existing jobs.json feed unchanged.")
        return
    OUT.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", len(jobs), "jobs")

if __name__ == "__main__":
    main()
