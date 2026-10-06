#!/usr/bin/env python3
import json,re,time
import collector_adzuna as adz
from collector_direct import collect_direct

def norm(s):return re.sub(r'[^a-z0-9]+','',(s or '').lower().replace('limited','').replace('ltd','').replace('plc',''))
def key(j):return (norm(j.get('company')),norm(re.sub(r'\b202[6-8]\b','',j.get('title',''))))

def collect_adzuna():
    found={}
    for q in adz.QUERIES:
        try:
            for x in adz.fetch(q,1):
                j=adz.make_job(x); j['source']='Adzuna'; j['direct']=False
                if j['eligibility']>=45 and j['score']>=62:
                    k=(j['company'].lower(),j['title'].lower(),j['location'].lower())
                    if k not in found or j['score']>found[k]['score']:found[k]=j
            time.sleep(.2)
        except Exception as e:print('Adzuna',q,e)
    print('Adzuna accepted:',len(found)); return list(found.values())

def main():
    direct=collect_direct(); broad=collect_adzuna(); merged={}
    for j in direct+broad:
        k=key(j); old=merged.get(k)
        if old is None or (j.get('direct') and not old.get('direct')) or (j.get('direct')==old.get('direct') and j.get('score',0)>old.get('score',0)): merged[k]=j
    jobs=list(merged.values()); jobs.sort(key=lambda j:(not j.get('direct',False),-j.get('score',0),j.get('age',999),j.get('company',''))); jobs=jobs[:300]
    if not jobs:print('No jobs; keeping old feed'); return
    adz.OUT.write_text(json.dumps(jobs,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Wrote',len(jobs),'jobs; direct',sum(1 for j in jobs if j.get('direct')))
if __name__=='__main__':main()
