import email.utils, html, json, re, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
import collector_adzuna as adz

UA='Launchboard/2.0'
GREENHOUSE=[('Marshall Wace','mw-tech-grad'),('Alpha FMC','alphafmcrolesearlycareers'),('Monzo','monzo')]
LEVER=[('Zopa','zopa'),('Bisnow','bisnow'),('Samba TV','sambatv')]
TEAMTAILOR=[('Metric','metricsearch-1723476068.teamtailor.com'),('Leyton','leyton.teamtailor.com'),('Codestone','codestone.teamtailor.com'),('Shuffle','shuffle.teamtailor.com')]
PINPOINT=[('MNI Markets','mnimarkets')]
UK=['united kingdom',' uk','london','manchester','birmingham','leeds','bristol','reading','edinburgh','glasgow','cardiff','nottingham','newcastle','liverpool','sheffield','oxford','cambridge','brighton','bournemouth','swindon','stevenage','croydon','wales','scotland','england','northern ireland']
EXCLUDE=['internship','summer intern','placement','apprentice','software engineer','software developer','developer','data engineer','machine learning','quant developer','quant research','algorithmic trader','director','vice president','head of','principal','senior manager']

def get_json(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)

def get_text(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=30) as r:return r.read().decode('utf-8','replace')

def text(s):
    s=html.unescape(s or ''); s=re.sub(r'<[^>]+>',' ',s)
    return re.sub(r'\s+',' ',html.unescape(s)).strip()

def uk(loc,desc=''):
    h=(' '+(loc or '')+' '+(desc or '')[:1500]).lower()
    return any(x in h for x in UK)

def bad(title,desc=''):
    h=((title or '')+' '+(desc or '')[:2500]).lower()
    return any(x in h for x in EXCLUDE)

def salary(desc):
    vals=[]
    for m in re.finditer(r'£\s?([0-9]{2,3}(?:,[0-9]{3})?)',desc or ''):
        try:
            v=int(m.group(1).replace(',',''))
            if 18000<=v<=200000: vals.append(v)
        except: pass
    vals=sorted(set(vals))
    if not vals:return None,None
    return vals[0],vals[-1]

def iso_date(v):
    if not v:return ''
    try:return datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(timezone.utc).isoformat()
    except:
        try:return email.utils.parsedate_to_datetime(v).astimezone(timezone.utc).isoformat()
        except:return ''

def convert(*,uid,company,title,loc,desc,url,source,created='',salary_min=None,salary_max=None,workplace='Check listing',deadline=None):
    title=adz.clean(title); loc=adz.clean(loc) or 'United Kingdom'; desc=text(desc)
    if not title or not url or not uk(loc,desc) or bad(title,desc):return None
    if salary_min is None and salary_max is None:salary_min,salary_max=salary(desc)
    raw={'id':uid,'title':title,'description':desc,'company':{'display_name':company},'location':{'display_name':loc},'salary_min':salary_min,'salary_max':salary_max,'created':iso_date(created),'redirect_url':url}
    j=adz.make_job(raw)
    if j['eligibility']<60 or j['score']<62:return None
    j['id']='direct-'+str(uid); j['source']=source; j['direct']=True; j['workplace']=workplace
    j['reason']=('Direct employer/ATS source · '+j['reason']).strip(' ·')
    j['tags']=list(dict.fromkeys((j.get('tags') or [])+[source,'Direct ATS']))
    if deadline:j['deadline']=deadline[:10]
    if '2027' in (title+' '+desc): j['score']=min(99,j['score']+8)
    return j

def greenhouse():
    out=[]
    for company,token in GREENHOUSE:
        try:
            data=get_json(f'https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true')
            for x in data.get('jobs',[]):
                j=convert(uid=f'gh-{token}-{x.get("id")}',company=company,title=x.get('title'),loc=(x.get('location') or {}).get('name'),desc=x.get('content'),url=x.get('absolute_url'),source=f'Greenhouse · {company}',created=x.get('updated_at'))
                if j:out.append(j)
        except Exception as e:print('Greenhouse',company,e)
    return out

def lever():
    out=[]
    for company,site in LEVER:
        try:
            rows=get_json(f'https://api.lever.co/v0/postings/{site}?mode=json')
            for x in rows if isinstance(rows,list) else []:
                c=x.get('categories') or {}; loc=c.get('location') or ''
                desc=' '.join([x.get('descriptionPlain') or x.get('description') or '',x.get('additionalPlain') or x.get('additional') or '',str(c.get('team') or ''),str(c.get('department') or '')])
                created=''
                if x.get('createdAt'):
                    try:created=datetime.fromtimestamp(int(x['createdAt'])/1000,tz=timezone.utc).isoformat()
                    except:pass
                j=convert(uid=f'lever-{site}-{x.get("id")}',company=company,title=x.get('text'),loc=loc,desc=desc,url=x.get('applyUrl') or x.get('hostedUrl'),source=f'Lever · {company}',created=created,workplace=x.get('workplaceType') or 'Check listing')
                if j:out.append(j)
        except Exception as e:print('Lever',company,e)
    return out

def teamtailor():
    out=[]
    for company,host in TEAMTAILOR:
        try:
            root=ET.fromstring(get_text(f'https://{host}/jobs.rss'))
            for item in root.findall('.//item'):
                title=item.findtext('title') or ''; link=item.findtext('link') or ''; desc=item.findtext('description') or ''
                for ch in item:
                    if ch.tag.endswith('encoded') and ch.text:desc+=' '+ch.text
                plain=text(desc); m=re.search(r'(?:Location|Locations):\s*([^|•\n<]{2,100})',plain,re.I)
                loc=m.group(1).strip() if m else ('London' if 'london' in plain.lower() else 'United Kingdom')
                j=convert(uid=f'tt-{host}-{abs(hash(link))}',company=company,title=title,loc=loc,desc=plain,url=link.rstrip('/')+'/applications/new' if link else '',source=f'Teamtailor · {company}',created=item.findtext('pubDate') or '')
                if j:out.append(j)
        except Exception as e:print('Teamtailor',company,e)
    return out

def pinpoint():
    out=[]
    for company,sub in PINPOINT:
        try:
            data=get_json(f'https://{sub}.pinpointhq.com/postings.json'); rows=data.get('data',[]) if isinstance(data,dict) else data
            for x in rows if isinstance(rows,list) else []:
                loc=x.get('location') or {}; loc=loc.get('name') if isinstance(loc,dict) else loc
                desc=' '.join(str(x.get(k) or '') for k in ['description','key_responsibilities','skills_knowledge_expertise','benefits'])
                j=convert(uid=f'pin-{sub}-{x.get("id")}',company=company,title=x.get('title'),loc=loc,desc=desc,url=x.get('application_form_url') or x.get('url'),source=f'Pinpoint · {company}',deadline=x.get('deadline_at'),salary_min=x.get('compensation_minimum'),salary_max=x.get('compensation_maximum'))
                if j:out.append(j)
        except Exception as e:print('Pinpoint',company,e)
    return out

def collect_direct():
    jobs=greenhouse()+lever()+teamtailor()+pinpoint()
    print('Direct ATS accepted:',len(jobs))
    return jobs
