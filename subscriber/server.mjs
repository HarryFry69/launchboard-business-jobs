/**
 * Launchboard subscriber gateway, Node 20+ and zero dependencies.
 *
 * Do not launch while the original GitHub repository and Pages site expose
 * jobs.json / employers.json publicly. Move the source and data to a PRIVATE
 * repository and disable public Pages before charging for exclusive access.
 */
import { createServer } from 'node:http';
import { createHmac, scryptSync, timingSafeEqual } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const COOKIE_AGE = 8 * 60 * 60;
const attempts = new Map();

export function requiredConfig(env) {
  const names = ['APP_ORIGIN','ACCESS_EMAIL','ACCESS_PASSWORD_HASH','SESSION_SECRET','STRIPE_SECRET_KEY','STRIPE_PRICE_ID'];
  const missing = names.filter(k => !env[k]);
  if (missing.length) throw new Error('Missing configuration: ' + missing.join(', '));
  const origin = new URL(env.APP_ORIGIN);
  if (!['http:','https:'].includes(origin.protocol) || origin.pathname !== '/' || origin.search || origin.hash)
    throw new Error('APP_ORIGIN must be a bare HTTP(S) origin, without a path');
  if (origin.protocol !== 'https:' && !['localhost','127.0.0.1'].includes(origin.hostname))
    throw new Error('Use HTTPS in production');
  if (!/^scrypt:[0-9a-f]{32,}:[0-9a-f]{128}$/i.test(env.ACCESS_PASSWORD_HASH))
    throw new Error('Generate ACCESS_PASSWORD_HASH using subscriber/hash-password.mjs');
  if (env.SESSION_SECRET.length < 32) throw new Error('SESSION_SECRET must contain at least 32 random characters');
  if (!/^price_[a-zA-Z0-9]+$/.test(env.STRIPE_PRICE_ID)) throw new Error('Invalid Stripe price ID');
}

function page(title, body) {
  return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<title>' + title + ' — Launchboard</title><style>' +
    '*{box-sizing:border-box}body{margin:0;min-height:100vh;background:#f2f6fa;color:#102546;font:16px/1.5 system-ui,Arial,sans-serif}' +
    'header{background:#0b2043;color:#fff;padding:20px;font-weight:800;font-size:23px}header span{color:#09c5ae}' +
    'main{background:#fff;max-width:560px;margin:55px auto;padding:34px;border:1px solid #dbe4ee;border-radius:14px;box-shadow:0 10px 32px #081e3610}' +
    'h1{line-height:1.18;font-size:30px}p{color:#4b6078}label{display:block;font-size:14px;font-weight:700;margin-top:16px}' +
    'input{width:100%;font-size:17px;padding:12px;border:1px solid #a6b8c9;border-radius:7px;margin-top:5px}' +
    'button,a.button{display:block;text-align:center;border:0;background:#12478b;color:white;text-decoration:none;padding:13px 17px;border-radius:7px;font:700 16px system-ui;cursor:pointer;margin-top:14px;width:100%}' +
    'button.secondary{background:#e8edf5;color:#122a48}.price{font-size:40px;color:#052d5c;font-weight:800}.price small{font-size:17px;font-weight:500}' +
    'small,.muted{color:#65758a}.error{color:#a72b2b}.success{color:#176f46}@media(max-width:620px){main{margin:22px 14px;padding:22px}}' +
    '</style></head><body><header>Launch<span>board</span></header><main>' + body + '</main></body></html>';
}

function loginPage(error='') {
  return page('Sign in', '<h1>Josh’s Launchboard</h1><p>Private job tracker. Sign in to manage your membership and access your listings.</p>' +
    (error ? '<p class="error">Email or password incorrect. Please try again.</p>' : '') +
    '<form method="POST" action="/login"><label>Email<input name="email" type="email" autocomplete="username" required maxlength="200"></label>' +
    '<label>Password<input name="password" type="password" autocomplete="current-password" required></label>' +
    '<button type="submit">Sign in</button></form>');
}

function dashboard(active, notice='') {
  const top = '<h1>Launchboard membership</h1>' +
    '<div class="price">£20 <small>/ month</small></div>' +
    '<p>Recurring monthly subscription. Secure checkout is hosted by Stripe. You will see the price and authorise payment before any charge.</p>';
  const actions = active
    ? '<p class="success">Subscription active. Job tracker access is enabled.</p><a class="button" href="/app">Open job tracker →</a>' +
      '<form action="/billing" method="POST"><button class="secondary">Manage or cancel subscription</button></form>'
    : '<p>There is no active subscription for this account. Job listings stay locked until payment is confirmed.</p>' +
      '<form action="/checkout" method="POST"><button>Subscribe for £20/month →</button></form>' +
      '<form action="/billing" method="POST"><button class="secondary">Manage existing billing</button></form>';
  return page('Membership', top + (notice === 'success' ? '<p>Stripe checkout returned. Checking your subscription status…</p>' : '') +
    actions + '<form method="POST" action="/logout"><button class="secondary">Sign out</button></form>');
}

function send(res, code, body, type='text/html; charset=utf-8', extra={}) {
  res.writeHead(code, {
    'Content-Type': type, 'Cache-Control':'private, no-store, max-age=0',
    'X-Content-Type-Options':'nosniff', 'X-Frame-Options':'DENY',
    'Referrer-Policy':'no-referrer', ...extra
  });
  res.end(body);
}

function redirect(res, target, extra={}) {
  send(res,303,'Redirecting…','text/plain; charset=utf-8',{Location:target,...extra});
}

function cookieName(env) { return new URL(env.APP_ORIGIN).protocol === 'https:' ? '__Host-lb_session' : 'lb_session'; }
function tokenSign(payload, key) {
  const input=Buffer.from(JSON.stringify(payload)).toString('base64url');
  const sig=createHmac('sha256',key).update(input).digest('base64url');
  return input+'.'+sig;
}
function tokenRead(input, env, now) {
  if (!input || input.length>2000) return false;
  const [encoded,provided,extra]=input.split('.');
  if (!encoded||!provided||extra) return false;
  const wanted=createHmac('sha256',env.SESSION_SECRET).update(encoded).digest();
  let actual;
  try{actual=Buffer.from(provided,'base64url')}catch{return false}
  if(actual.length!==wanted.length||!timingSafeEqual(actual,wanted))return false;
  try{const p=JSON.parse(Buffer.from(encoded,'base64url').toString('utf8'));
    return p.sub===env.ACCESS_EMAIL.toLowerCase() && Number.isFinite(p.exp) && p.exp>now;
  }catch{return false}
}
function readCookie(req,env,now) {
  const name=cookieName(env);
  const line=(req.headers.cookie||'').split(';').map(s=>s.trim()).find(s=>s.startsWith(name+'='));
  return line ? tokenRead(line.slice(name.length+1),env,now) : false;
}
function setCookie(env,token,maxAge) {
  return cookieName(env)+'='+token+'; Path=/; HttpOnly; SameSite=Lax; Max-Age='+maxAge+
    (new URL(env.APP_ORIGIN).protocol==='https:'?'; Secure':'');
}
function verifyPassword(password, stored) {
  const [, saltHex, digestHex] = stored.split(':');
  const calculated=scryptSync(password,Buffer.from(saltHex,'hex'),64);
  const expected=Buffer.from(digestHex,'hex');
  return expected.length===calculated.length && timingSafeEqual(expected,calculated);
}
async function bodyForm(req) {
  let text='';
  for await(const chunk of req) {
    text+=chunk.toString();
    if(text.length>4096)throw new Error('Request body too large');
  }
  return new URLSearchParams(text);
}
function isSameOrigin(req,env) {
  const origin=req.headers.origin;
  return !origin || origin===env.APP_ORIGIN;
}
async function api(env,method,endpoint,fields) {
  const r=await fetch('https://api.stripe.com'+endpoint,{
    method,headers:{Authorization:'Bearer '+env.STRIPE_SECRET_KEY,
      ...(method==='POST'?{'Content-Type':'application/x-www-form-urlencoded'}:{})},
    ...(method==='POST'?{body:new URLSearchParams(fields)}:{})
  });
  if(!r.ok)throw new Error('Stripe API error '+r.status);
  return r.json();
}
function isActiveSubscription(sub, priceId) {
  return sub.status==='active' &&
    Array.isArray(sub.items?.data) &&
    sub.items.data.some(item=>item.price?.id===priceId);
}
async function customerRecords(env,stripeRequest) {
  const q=new URLSearchParams({email:env.ACCESS_EMAIL,limit:'100'});
  const data=await stripeRequest(env,'GET','/v1/customers?'+q.toString());
  return (data.data||[]).filter(c=>c.id && !c.deleted && c.email?.toLowerCase()===env.ACCESS_EMAIL.toLowerCase());
}
async function membership(env,stripeRequest) {
  const customers=await customerRecords(env,stripeRequest);
  for(const customer of customers) {
    const q=new URLSearchParams({customer:customer.id,status:'all',limit:'100'});
    const subs=await stripeRequest(env,'GET','/v1/subscriptions?'+q.toString());
    if((subs.data||[]).some(s=>isActiveSubscription(s,env.STRIPE_PRICE_ID)))
      return {active:true,customer:customer.id};
  }
  return {active:false,customer:customers[0]?.id||null};
}
async function redirectToStripe(res, data) {
  if(!data?.url || !/^https:\/\/(checkout|billing)\.stripe\.com\//.test(data.url))
    throw new Error('Unexpected Stripe redirect URL');
  redirect(res,data.url);
}
function clientId(req) { return req.socket.remoteAddress || 'unknown'; }
function rateLimited(ip,now) {
  const slot=attempts.get(ip);
  if(!slot||now-slot.since>15*60*1000){attempts.set(ip,{since:now,count:1});return false}
  slot.count++;
  return slot.count>7;
}

export function createHandler({env=process.env,stripeRequest=api,now=()=>Date.now(),read=readFile}={}) {
  requiredConfig(env);
  return async function handler(req,res) {
    try {
      const target=new URL(req.url,'http://localhost');
      const pathname=target.pathname;
      const timestamp=now();
      const loggedIn=readCookie(req,env,Math.floor(timestamp/1000));
      if(pathname==='/healthz' && req.method==='GET') return send(res,200,'ok','text/plain');
      if(pathname==='/login'&&req.method==='POST') {
        if(!isSameOrigin(req,env))return send(res,403,'Forbidden','text/plain');
        if(rateLimited(clientId(req),timestamp))return send(res,429,'Too many attempts; retry later','text/plain');
        const form=await bodyForm(req);
        const email=(form.get('email')||'').toLowerCase().trim();
        const password=form.get('password')||'';
        const valid=password.length<=200 && verifyPassword(password,env.ACCESS_PASSWORD_HASH) &&
          email===env.ACCESS_EMAIL.toLowerCase();
        if(!valid)return send(res,401,loginPage('incorrect'));
        attempts.delete(clientId(req));
        const session=tokenSign({sub:email,exp:Math.floor(timestamp/1000)+COOKIE_AGE},env.SESSION_SECRET);
        return redirect(res,'/',{'Set-Cookie':setCookie(env,session,COOKIE_AGE)});
      }
      if(pathname==='/logout' && req.method==='POST'){
        if(!isSameOrigin(req,env))return send(res,403,'Forbidden','text/plain');
        return redirect(res,'/',{'Set-Cookie':setCookie(env,'',0)});
      }
      if(pathname==='/' && req.method==='GET') {
        if(!loggedIn)return send(res,200,loginPage());
        const access=await membership(env,stripeRequest);
        return send(res,200,dashboard(access.active,target.searchParams.get('checkout')||''));
      }
      if(pathname==='/app'||pathname==='/api/jobs'||pathname==='/api/employers') {
        if(req.method!=='GET')return send(res,405,'Method not allowed','text/plain');
        if(!loggedIn)return pathname==='/app'?redirect(res,'/'):send(res,401,'{"error":"Sign in required"}','application/json');
        const access=await membership(env,stripeRequest);
        if(!access.active)return pathname==='/app'?redirect(res,'/'):send(res,403,'{"error":"Active subscription required"}','application/json');
        if(pathname==='/api/jobs'||pathname==='/api/employers'){
          const data=await read(join(ROOT,pathname==='/api/jobs'?'jobs.json':'employers.json'));
          return send(res,200,data,'application/json; charset=utf-8');
        }
        let html=await read(join(ROOT,'index.html'),'utf8');
        const withoutInline=html.replace(/let jobs = \[[^\n]*\];\s*const store=/,'let jobs = [];\nconst store=');
        if(withoutInline===html)throw new Error('Inline job data could not be removed: refusing to serve');
        html=withoutInline.replace("fetch('jobs.json?ts='","fetch('/api/jobs?ts='")
          .replace("fetch('employers.json?ts='","fetch('/api/employers?ts='");
        return send(res,200,html);
      }
      if(!loggedIn) return redirect(res,'/');
      if(pathname==='/checkout' && req.method==='POST') {
        if(!isSameOrigin(req,env))return send(res,403,'Forbidden','text/plain');
        const status=await membership(env,stripeRequest);
        if(status.active)return redirect(res,'/app');
        const price=await stripeRequest(env,'GET','/v1/prices/'+encodeURIComponent(env.STRIPE_PRICE_ID));
        if(!price.active||price.currency!=='gbp'||price.unit_amount!==2000||
          price.recurring?.interval!=='month'||(price.recurring.interval_count||1)!==1)
          throw new Error('Stripe price must be exactly GBP 20.00 each month');
        const customer=status.customer||(
          await stripeRequest(env,'POST','/v1/customers',{email:env.ACCESS_EMAIL,
            'metadata[app]':'Launchboard'})
        ).id;
        const data=await stripeRequest(env,'POST','/v1/checkout/sessions',{
          mode:'subscription',customer,'line_items[0][price]':env.STRIPE_PRICE_ID,
          'line_items[0][quantity]':'1',success_url:env.APP_ORIGIN+'/?checkout=success',
          cancel_url:env.APP_ORIGIN+'/?checkout=cancel',
          client_reference_id:'launchboard-josh'
        });
        return redirectToStripe(res,data);
      }
      if(pathname==='/billing' && req.method==='POST') {
        if(!isSameOrigin(req,env))return send(res,403,'Forbidden','text/plain');
        const status=await membership(env,stripeRequest);
        if(!status.customer)return redirect(res,'/');
        const data=await stripeRequest(env,'POST','/v1/billing_portal/sessions',{
          customer:status.customer,return_url:env.APP_ORIGIN+'/'});
        return redirectToStripe(res,data);
      }
      return send(res,404,'Not found','text/plain');
    }catch(err) {
      console.error('Launchboard gateway:',err.message);
      return send(res,503,page('Unavailable','<h1>Temporarily unavailable</h1><p>Membership verification could not be completed. No job data has been exposed. Please try again later.</p>'));
    }
  };
}

if (process.argv[1] && resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try{
    const listener=createServer(createHandler());
    listener.listen(Number(process.env.PORT)||3000,'0.0.0.0',()=>console.log('Launchboard gateway listening'));
  }catch(err){console.error(err.message);process.exit(1)}
}
