import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { randomBytes, scryptSync } from 'node:crypto';
import { createHandler } from './server.mjs';

const PASSWORD='a-long-testing-password-123';
const salt=randomBytes(16);
const env={
  APP_ORIGIN:'http://localhost',
  ACCESS_EMAIL:'josh@example.com',
  ACCESS_PASSWORD_HASH:'scrypt:'+salt.toString('hex')+':'+scryptSync(PASSWORD,salt,64).toString('hex'),
  SESSION_SECRET:'test-secret-not-for-production-'+randomBytes(32).toString('hex'),
  STRIPE_SECRET_KEY:'sk_test_placeholder',
  STRIPE_PRICE_ID:'price_example123'
};
async function harness() {
  let status='incomplete';
  let price=2000;
  let checkoutCount=0;
  let ts=Date.now();
  const stripeRequest=async (_env,method,endpoint,fields)=>{
    if(endpoint.startsWith('/v1/customers?'))return {data:[{id:'cus_josh',email:'josh@example.com'}]};
    if(endpoint.startsWith('/v1/subscriptions?'))return {data:[{
      status,items:{data:[{price:{id:'price_example123'}}]}
    }]};
    if(endpoint.startsWith('/v1/prices/'))return {active:true,currency:'gbp',
      unit_amount:price,recurring:{interval:'month',interval_count:1}};
    if(endpoint==='/v1/checkout/sessions'){
      assert.equal(method,'POST');
      assert.equal(fields.mode,'subscription');
      assert.equal(fields.customer,'cus_josh');
      assert.equal(fields['line_items[0][price]'],'price_example123');
      assert.equal(fields['line_items[0][quantity]'],'1');
      checkoutCount++;
      return {url:'https://checkout.stripe.com/c/pay/mock-session'};
    }
    if(endpoint==='/v1/billing_portal/sessions')return {url:'https://billing.stripe.com/p/mock-session'};
    throw new Error('Unknown Stripe endpoint '+endpoint);
  };
  const server=createServer(createHandler({env,stripeRequest,now:()=>ts}));
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const port=server.address().port;
  const base='http://127.0.0.1:'+port;
  async function request(p,opts={}) {
    return fetch(base+p,{redirect:'manual',...opts});
  }
  const stop=()=>new Promise((resolve,reject)=>server.close(err=>err?reject(err):resolve()));
  return {request,stop,setStatus:x=>status=x,setPrice:x=>price=x,
    changeTime:delta=>ts+=delta,get checkoutCount(){return checkoutCount;}};
}
test('unpaid and anonymous users cannot read either data feed or application',async()=>{
  const x=await harness();
  try{
    assert.equal((await x.request('/api/jobs')).status,401);
    assert.equal((await x.request('/api/employers')).status,401);
    assert.equal((await x.request('/app')).status,303);
    assert.equal((await x.request('/')).status,200);
  }finally{await x.stop()}
});
test('login, paid access, cancellation and signed-session expiry',async()=>{
  const x=await harness();
  try{
    const bad=await x.request('/login',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},
      body:new URLSearchParams({email:'josh@example.com',password:'wrong'})});
    assert.equal(bad.status,401);
    const ok=await x.request('/login',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},
      body:new URLSearchParams({email:'josh@example.com',password:PASSWORD})});
    assert.equal(ok.status,303);
    const cookie=ok.headers.get('set-cookie').split(';')[0];
    assert.equal((await x.request('/api/jobs',{headers:{cookie}})).status,403);
    assert.equal((await x.request('/api/employers',{headers:{cookie}})).status,403);
    assert.equal((await x.request('/app',{headers:{cookie}})).status,303);
    x.setStatus('active');
    let result=await x.request('/api/jobs',{headers:{cookie}});
    assert.equal(result.status,200);
    assert.ok((await result.json()).length>0);
    result=await x.request('/api/employers',{headers:{cookie}});
    assert.equal(result.status,200);
    assert.ok((await result.json()).length>0);
    result=await x.request('/app',{headers:{cookie}});
    assert.equal(result.status,200);
    const html=await result.text();
    assert.ok(html.includes("fetch('/api/jobs?ts="));
    assert.ok(html.includes("fetch('/api/employers?ts="));
    assert.ok(html.includes('let jobs = [];'));
    assert.ok(!html.includes('"id": "protiviti-2027"'), 'inline source data must be absent');
    x.setStatus('past_due');
    assert.equal((await x.request('/api/jobs',{headers:{cookie}})).status,403);
    x.setStatus('canceled');
    assert.equal((await x.request('/api/jobs',{headers:{cookie}})).status,403);
    x.setStatus('active');
    x.changeTime(9*60*60*1000);
    assert.equal((await x.request('/api/jobs',{headers:{cookie}})).status,401);
  }finally{await x.stop()}
});
test('Stripe Checkout is correct monthly plan, and never automatically charged',async()=>{
  const x=await harness();
  try{
    const ok=await x.request('/login',{method:'POST',
      body:new URLSearchParams({email:'josh@example.com',password:PASSWORD})});
    const cookie=ok.headers.get('set-cookie').split(';')[0];
    assert.equal(x.checkoutCount,0);
    const checkout=await x.request('/checkout',{method:'POST',headers:{cookie}});
    assert.equal(checkout.status,303);
    assert.ok(checkout.headers.get('location').startsWith('https://checkout.stripe.com/'));
    assert.equal(x.checkoutCount,1);
    x.setPrice(1500);
    assert.equal((await x.request('/checkout',{method:'POST',headers:{cookie}})).status,503);
    assert.equal(x.checkoutCount,1);
    x.setPrice(2000);
    x.setStatus('active');
    const already=await x.request('/checkout',{method:'POST',headers:{cookie}});
    assert.equal(already.status,303);
    assert.equal(already.headers.get('location'),'/app');
    assert.equal(x.checkoutCount,1);
    const portal=await x.request('/billing',{method:'POST',headers:{cookie}});
    assert.equal(portal.status,303);
    assert.ok(portal.headers.get('location').startsWith('https://billing.stripe.com/'));
  }finally{await x.stop()}
});
test('tampered cookies and wrong username are denied',async()=>{
  const x=await harness();
  try{
    let r=await x.request('/login',{method:'POST',
      body:new URLSearchParams({email:'attacker@example.com',password:PASSWORD})});
    assert.equal(r.status,401);
    r=await x.request('/login',{method:'POST',
      body:new URLSearchParams({email:'josh@example.com',password:PASSWORD})});
    const cookie=r.headers.get('set-cookie').split(';')[0];
    const tampered=cookie.replace(/.$/,'x');
    assert.equal((await x.request('/api/jobs',{headers:{cookie:tampered}})).status,401);
  }finally{await x.stop()}
});
