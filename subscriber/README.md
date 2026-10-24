# Launchboard: private £20/month subscriber gateway

This is a deployable Node 20+ HTTP server that protects Launchboard's
existing UI, jobs.json and employers.json behind a password AND a Stripe
£20/month active subscription. No runtime third-party packages are needed.

IMPORTANT: This is staged code, not a live paywall. The main repository
and GitHub Pages site are currently public. Anyone can read the source
jobs.json through those public URLs until you change the architecture.

## Steps to launch

1. Run tests with: node --test subscriber/subscriber.test.mjs
2. Have Josh agree to the £20/month recurring subscription. Obtain his
   login email privately. Set ACCESS_EMAIL to that address.
3. In Stripe TEST mode, create the Launchboard Membership product and an
   active recurring Price of precisely GBP £20.00 per MONTH. Copy the
   price_ identifier. Enable the Stripe customer portal with cancellation.
4. Create a PRIVATE GitHub repository containing this code, the current
   index.html and continuously updated jobs.json and employers.json at its
   root. Make the old repository private and turn off GitHub Pages, or
   remove its data from public access. The private repo may connect to a
   Node web host (for example, Render). You may need to move or replicate
   the jobs collector into the private repo.
5. Start command from repository root: node subscriber/server.mjs
   Run Node 20+ on the hosting service. Use a permanent HTTPS URL.
6. On a trusted machine run: cd subscriber && npm run hash-password
   Choose a strong password. It prints a scrypt password HASH and a random
   session secret. Share the password with Josh securely. Keep both values
   in private hosting environment settings; do not commit either.
7. Set APP_ORIGIN, ACCESS_EMAIL, ACCESS_PASSWORD_HASH, SESSION_SECRET,
   STRIPE_SECRET_KEY, STRIPE_PRICE_ID in the host's secrets (see
   subscriber/.env.example). APP_ORIGIN must equal the publicly accessed
   HTTPS origin and contain no trailing slash or path. Never give
   Stripe's secret key to browser JavaScript or a public repository.
8. Using sk_test_ and test-mode price_, test: wrong password, correct
   login, unpaid /api/jobs denied, Stripe Checkout, successful test
   payment, paid /api/jobs allowed, customer billing portal, scheduled
   cancellation, renewal failure and access after period expiration.
9. Only then replace test credentials with live Stripe API credentials
   and a LIVE GBP £20 monthly recurring price. Josh must personally
   authorise payment via hosted Checkout. No code here charges him
   automatically, and nothing has yet been charged.

## Endpoints and access controls

- GET / : password login or Stripe-backed subscription dashboard
- POST /login : log in the one approved email with salted scrypt password
- POST /logout : clear the signed HttpOnly session cookie
- POST /checkout : start Stripe-hosted £20/month subscription Checkout
- POST /billing : open Stripe Billing portal for cancellation or payment
- GET /app : full Launchboard HTML only with active subscription
- GET /api/jobs and /api/employers : protected JSON only after live check
- GET /healthz : non-sensitive status response

The app checks Stripe directly on every protected request; it does not
trust front-end flags, query strings or cookies as proof of payment.
Only Stripe status ACTIVE and the exact configured recurring price unlock
access. Pending, unpaid, trialing, past_due, paused and cancelled
subscriptions are denied. Scheduled cancel-at-period-end subscriptions
normally remain ACTIVE until the paid interval ends, when access revokes.
A Stripe outage denies protected access rather than leaking data.

The Stripe price is checked for currency GBP, amount 2000 pence and
recurrence every month when Checkout starts. The £20 amount is
informational until Josh personally approves a subscription.

For a single known subscriber, a signed 8-hour secure session cookie
and in-memory login throttle are adequate for a staged pilot. For a
public multi-user SaaS, replace this simple authentication layer with
managed identities, durable rate limiting, a real customer/account
database, billing webhooks and audit logs.

The front end currently stores application statuses and notes in the
user's browser localStorage. That information does not sync across
devices, even after you deploy this server.

Before offering paid access commercially, arrange customer support and
easy cancellation; address UK consumer, tax and privacy obligations
and the job-data provider's licensing/commercial-use requirements.
