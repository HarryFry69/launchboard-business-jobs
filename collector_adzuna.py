#!/usr/bin/env python3
"""
Launchboard automatic UK business/management graduate-job collector.

Requires:
  ADZUNA_APP_ID
  ADZUNA_APP_KEY

Writes:
  jobs.json

Designed to run on GitHub Actions every few hours.
"""
import json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

APP_ID = os.environ["ADZUNA_APP_ID"]
APP_KEY = os.environ["ADZUNA_APP_KEY"]
OUT = Path(__file__).with_name("jobs.json")

QUERIES = [
    "graduate business",
    "graduate consultant",
    "business development executive",
    "revenue operations analyst",
    "commercial graduate",
    "graduate business analyst",
    "graduate strategy",
    "graduate operations",
    "graduate account executive",
    "graduate recruitment consultant",
    "entry level business development",
    "entry level commercial analyst",
]

POSITIVE = {
    "graduate": 18, "entry level": 16, "entry-level": 16,
    "business development": 14, "commercial": 13, "consult": 13,
    "revenue operations": 17, "business analyst": 14, "operations analyst": 12,
    "strategy": 12, "fintech": 10, "financial markets": 10, "payments": 10,
    "account executive": 9, "client": 5, "partnership": 8, "sales": 5,
}
NEGATIVE = {
    "senior": -28, "manager": -18, "director": -35, "head of": -35,
    "5 years": -45, "4 years": -40, "3 years": -34, "2 years": -26,
    "minimum 2 years": -35, "experienced hire": -35,
}
CATS = [
    ("Revenue Operations", ["revenue operations","revops"]),
    ("Consulting", ["consultant","consulting","advisory"]),
    ("Business Development", ["business development","account executive","sales development","partnership"]),
    ("Recruitment", ["recruitment","executive search","talent"]),
    ("Commercial", ["commercial","business analyst","strategy","operations"]),
]

def fetch(query, page=1):
    params = {
        "app_id": APP_ID, "app_key": APP_KEY, "results_per_page": 50,
        "what": query, "sort_by": "date", "content-type": "application/json",
    }
    url = f"https://api.adzuna.com/v1/api/jobs/gb/search/{page}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent":"Launchboard/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("results", [])

def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()

def category(text):
    t=text.lower()
    for name, keys in CATS:
        if any(k in t for k in keys): return name
    return "Commercial"

def score_job(title, desc):
    t=(title+" "+desc).lower()
    score=48
    for k,v in POSITIVE.items():
        if k in t: score += v
    for k,v in NEGATIVE.items():
        if k in t: score += v
    # Strongly prefer explicit graduate/entry-level signals.
    if not any(x in t for x in ["graduate","entry level","entry-level","junior","trainee"]):
        score -= 18
    return max(0,min(99,score))

def eligibility(title, desc):
    t=(title+" "+desc).lower()
    if any(x in t for x in ["director","head of","senior manager","5 years","4 years","3 years"]):
        return 25
    if "2 years" in t or "minimum 2 years" in t:
        return 45
    if any(x in t for x in ["graduate","entry level","entry-level","junior","trainee","no experience"]):
        return 100
    return 78

def salary_text(x):
    lo=x.get("salary_min"); hi=x.get("salary_max")
    if lo and hi:
        lo=int(round(lo)); hi=int(round(hi))
        return f"£{lo:,}–£{hi:,}", hi
    if lo:
        lo=int(round(lo)); return f"From £{lo:,}", lo
    if hi:
        hi=int(round(hi)); return f"Up to £{hi:,}", hi
    return "Not specified", 0

def age_days(created):
    if not created: return 999
    try:
        dt=datetime.fromisoformat(created.replace("Z","+00:00"))
        return max(0,(datetime.now(timezone.utc)-dt.astimezone(timezone.utc)).days)
    except Exception:
        return 999

def make_job(x):
    title=clean(x.get("title"))
    desc=clean(x.get("description"))
    company=clean((x.get("company") or {}).get("display_name")) or "Company"
    loc=clean((x.get("location") or {}).get("display_name")) or "United Kingdom"
    sal,salmax=salary_text(x)
    s=score_job(title,desc); e=eligibility(title,desc)
    created=x.get("created") or ""
    age=age_days(created)
    ident=str(x.get("id") or abs(hash((title,company,loc))))
    why=[]
    text=(title+" "+desc).lower()
    if "graduate" in text: why.append("Explicit graduate signal")
    if "entry level" in text or "entry-level" in text: why.append("Entry-level signal")
    if any(k in text for k in ["fintech","payments","financial markets"]): why.append("Finance/FinTech exposure")
    if any(k in text for k in ["business development","commercial","revenue operations","strategy","consult"]): why.append("Strong role-family match")
    if salmax: why.append("Salary disclosed")
    return {
        "id":"adz-"+ident, "company":company, "initials":"".join(w[0] for w in company.split()[:2]).upper(),
        "title":title, "category":category(title+" "+desc), "location":loc,
        "workplace":"Check listing", "salary":sal, "salaryMax":salmax,
        "level":"Graduate" if "graduate" in text else "Entry Level",
        "posted": created[:10] if created else "Recent", "age":age, "new":age<=7,
        "score":s, "eligibility":e, "priority":"A+" if s>=94 else "A" if s>=85 else "B",
        "sector":"Business / Commercial",
        "url":x.get("redirect_url") or "https://www.adzuna.co.uk/",
        "reason":" · ".join(why[:3]) or "Potential match based on title, seniority and commercial/business keywords.",
        "tags":[category(title+" "+desc),"UK","Graduate / Entry Level"],
        "summary":desc[:420] + ("…" if len(desc)>420 else ""),
        "fit":why[:4] or ["UK role","Potential business/commercial match"],
        "caution":"Open the original listing to confirm start date, degree requirements and exact experience expectations."
    }

def main():
    found={}
    for q in QUERIES:
        for page in (1,):
            try:
                for x in fetch(q,page):
                    j=make_job(x)
                    if j["eligibility"] >= 45 and j["score"] >= 62:
                        key=(j["company"].lower(),j["title"].lower(),j["location"].lower())
                        if key not in found or j["score"] > found[key]["score"]:
                            found[key]=j
                time.sleep(.25)
            except Exception as exc:
                print("query failed:",q,page,exc)
    jobs=sorted(found.values(), key=lambda j:(-j["score"],j["age"]))[:250]
    if not jobs:
        print("No jobs returned; keeping the existing jobs.json feed unchanged.")
        return
    OUT.write_text(json.dumps(jobs,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Wrote",len(jobs),"jobs")

if __name__=="__main__":
    main()
