#!/usr/bin/env python3
import json, re, time
from pathlib import Path
import collector_adzuna as adz
from collector_direct import collect_direct

CITIES = [
    "london","manchester","birmingham","leeds","bristol","reading","edinburgh",
    "glasgow","cardiff","nottingham","newcastle","liverpool","sheffield",
    "oxford","cambridge","brighton","bournemouth","swindon","stevenage",
    "croydon","belfast","aberdeen","southampton","chelmsford","perth"
]

def norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower()
                  .replace("limited", "").replace("ltd", "").replace("plc", ""))

def company_key(name):
    n = norm(name)
    aliases = {
        "bdouk": "bdo",
        "pricewaterhousecoopers": "pwc",
        "ernstyoung": "ey",
        "grantthorntonuk": "grantthornton",
        "rsmuk": "rsm",
        "forvismazarsuk": "forvismazars",
    }
    return aliases.get(n, n)

def loc_key(loc):
    s = (loc or "").lower()
    hits = [c for c in CITIES if c in s]
    if hits:
        return "+".join(sorted(hits))
    if any(x in s for x in ["multiple", "various", "nationwide", "united kingdom", "uk"]):
        return "uk-multiple"
    return norm(s)

def key(j):
    title = re.sub(r"\b202[6-8]\b", "", j.get("title", ""), flags=re.I)
    return (company_key(j.get("company")), norm(title), loc_key(j.get("location")))

def collect_priority():
    p = Path(__file__).with_name("priority_jobs.json")
    if not p.exists():
        return []
    try:
        rows = json.loads(p.read_text(encoding="utf-8"))
        out = []
        for j in rows if isinstance(rows, list) else []:
            if not isinstance(j, dict) or not j.get("title") or not j.get("url"):
                continue
            j["direct"] = True
            j.setdefault("source", "Official employer")
            j.setdefault("age", 0)
            j.setdefault("new", False)
            j.setdefault("eligibility", 100)
            j.setdefault("score", 90)
            j.setdefault("priority", "A" if j["score"] < 94 else "A+")
            out.append(j)
        print("Priority employer roles:", len(out))
        return out
    except Exception as e:
        print("Priority employer ERROR", e)
        return []

def collect_adzuna():
    found = {}
    for q in adz.QUERIES:
        try:
            for x in adz.fetch(q, 1):
                j = adz.make_job(x)
                j["source"] = "Adzuna"
                j["direct"] = False
                if j["eligibility"] >= 60 and j["score"] >= 60 and adz.relevant(j["title"], x.get("description") or ""):
                    k = (j["company"].lower(), j["title"].lower(), j["location"].lower())
                    if k not in found or j["score"] > found[k]["score"]:
                        found[k] = j
            time.sleep(.15)
        except Exception as e:
            print("Adzuna", q, "ERROR", e)
    print("Adzuna accepted:", len(found))
    return list(found.values())

def main():
    priority = collect_priority()
    direct = collect_direct()
    broad = collect_adzuna()
    merged = {}

    # Prefer a direct ATS version when two records are materially the same,
    # but never allow a weak direct job to outrank a much stronger fit.
    for j in priority + direct + broad:
        k = key(j)
        old = merged.get(k)
        if old is None:
            merged[k] = j
            continue

        if j.get("direct") and not old.get("direct") and j.get("score", 0) >= old.get("score", 0) - 5:
            merged[k] = j
        elif j.get("score", 0) > old.get("score", 0):
            merged[k] = j

    jobs = list(merged.values())
    jobs.sort(key=lambda j: (
        -j.get("score", 0),
        not j.get("direct", False),
        j.get("age", 999),
        j.get("company", ""),
        j.get("location", "")
    ))
    jobs = jobs[:350]

    if not jobs:
        print("No jobs; keeping old feed")
        return

    adz.OUT.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", len(jobs), "jobs; direct", sum(1 for j in jobs if j.get("direct")))

if __name__ == "__main__":
    main()
