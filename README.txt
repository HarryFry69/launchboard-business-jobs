TRACKR-STYLE TABLE
The front end now uses a dense spreadsheet/table layout rather than job cards.

LAUNCHBOARD — 2027 BUSINESS GRADUATE JOB TRACKER

WHAT IT DOES
- Trackr-style responsive job board
- Personal fit + eligibility scoring
- Search, category/location filters and sorting
- Saved jobs + application tracking
- Direct Apply links to the original vacancy
- Browser-local state: no user account/database required
- Starter vacancies included until the live feed runs

AUTOMATIC LIVE FEED
The package includes:
- jobs.json — live feed displayed by the hosted site
- collector_adzuna.py — UK graduate/entry-level business-job collector
- .github/workflows/update_jobs.yml — runs every 4 hours

The collector currently makes 12 API calls per refresh (one 50-result page for each search phrase).
At 6 refreshes/day that is about:
- 72 calls/day
- 504 calls/week
- ~2,160 calls/30-day month
This stays within Adzuna's default 250/day, 1,000/week and 2,500/month limits.

QUICKEST DEPLOYMENT
1. Create a FREE GitHub repository, e.g. launchboard-business-jobs.
2. Upload the CONTENTS of this folder to the repository root.
3. Create a free Adzuna developer account and obtain APP_ID + APP_KEY.
4. In GitHub:
   Settings → Secrets and variables → Actions → New repository secret
   Add:
     ADZUNA_APP_ID
     ADZUNA_APP_KEY
5. Go to Actions → Update graduate jobs → Run workflow.
   This should replace the 6 starter jobs with the live scored feed.
6. Go to Settings → Pages:
   Source = Deploy from a branch
   Branch = main
   Folder = /(root)
   Save.
7. GitHub will publish the site at:
   https://YOUR-GITHUB-USERNAME.github.io/launchboard-business-jobs/
8. Send that URL to your brother.

ONGOING
- GitHub Actions runs every 4 hours.
- It searches multiple graduate/entry-level business role families.
- It deduplicates results.
- It penalises senior and 2+ years experience roles.
- It scores fit and eligibility.
- It rewrites jobs.json.
- The commit triggers GitHub Pages to publish the new feed.
- No manual job entry is required for ordinary updates.

SOURCES / NEXT LAYER
Adzuna provides broad UK coverage. For better quality later, add direct public ATS feeds
(Greenhouse / Lever / selected employer career sites) and merge them before deduplication.

IMPORTANT
- Adzuna requires attribution when its listings are published; the site footer includes Jobs by Adzuna.
- Application links go to the external listing/application destination.


CURRENT SNAPSHOT
The packaged board contains 43 opportunities checked/assembled on 6 October 2026. Some employers may close high-volume graduate roles early, so the live application page remains authoritative.
