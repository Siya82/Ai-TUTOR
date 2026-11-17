# ADR-033: Deploying THUTOra to Google Cloud (staging and production)

> **On hold (17 Nov 2026):** Siya paused the GCP move; fix the issues in `CODE_REVIEW_2026-11-17.md` first.

**Status:** Proposed. Plan only; no infrastructure created yet.
**Date:** 17 November 2026

## Context

THUTOra runs only on Siya's laptop. Siya chose GCP as the long-term platform
(14 Nov 2026) and has a free-trial account. The goals: a pilot school can use
the app; development carries on locally as today; nothing depends on one
machine; and the costs fit a bootstrapped startup.

Prices and limits below were checked on 17 Nov 2026 from Google's pages and
pricing trackers. They change, so re-check them in the console before
committing.

## What the app needs from a host

| Today (laptop) | In the cloud |
|---|---|
| FastAPI via uvicorn | A container on **Cloud Run** |
| Postgres 16 + pgvector in Docker | **Cloud SQL for PostgreSQL** (pgvector is supported) |
| React/Vite dev server | Static build on **Firebase Hosting** |
| `backend/.env` secrets | **Secret Manager** |
| `uploads/attachments/` on disk | **Cloud Storage** bucket (Cloud Run's disk doesn't persist) |
| `content_sources/books/*.epub` on disk | Cloud Storage bucket, mounted into Cloud Run |
| `alembic upgrade head` by hand | A **Cloud Run job** that runs each deploy |
| Pushing by hand | **GitHub Actions** builds and deploys from `main` |

## Decision

### Region: Johannesburg (`africa-south1`) for everything holding learner data

Google opened the Johannesburg region in January 2024. Keeping the database,
backend and file buckets there keeps learners' data in South Africa, which is
the simplest POPIA position and the lowest latency for SA schools. Cloud SQL
supports the region (including shared-core machines), and so does Cloud Run.
Cloud Run bills Johannesburg at **Tier 2** prices (higher than the US).

Two consequences of this region choice:

- **Custom domains.** Cloud Run's built-in domain mapping isn't available in
  `africa-south1`. Firebase Hosting rewrites to Cloud Run don't list it
  either. So: the **frontend** gets the custom domain on Firebase Hosting
  (static files only, served globally), and the **API** starts on its own
  `*.run.app` URL, which the frontend calls directly over HTTPS with CORS. A
  custom API domain (`api.…`) later needs a global external Application Load
  Balancer, which has a fixed monthly cost, so it's deferred until it's worth
  paying for.
- **Third-party AI is still offshore.** Claude (and OpenAI embeddings, if
  enabled) process outside South Africa whatever GCP region we pick. See
  POPIA below.

### Two separate GCP projects: `thutora-staging` and `thutora-prod`

Each has its own Cloud SQL instance, buckets, secrets and service accounts.
Staging gets the seed data and test accounts; **production never gets seed
data or dev accounts, and real learner data is never copied out of it.**
Separate projects mean a staging mistake can't touch production, and billing
is visible per environment.

### Services and sizes (pilot scale)

| Piece | Staging | Production (pilot) |
|---|---|---|
| Cloud Run `thutora-api` | min 0 instances (scales to zero), 1 vCPU / 512 MiB | min 0 at first; min 1 once schools use it daily (avoids cold starts) |
| Cloud SQL Postgres 16, Enterprise | `db-f1-micro` (about $8/month; no SLA) | `db-g1-small` to start (about $26/month in us-central1; also no SLA) → a dedicated-core machine once a school depends on it; automated backups + point-in-time recovery |
| Cloud Storage | `…-staging-uploads`, `…-staging-books` | `…-prod-uploads` (private, versioned), `…-prod-books` |
| Firebase Hosting | `staging.<domain>` | `app.<domain>` |
| Secret Manager | `ANTHROPIC_API_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL`, `OPENAI_API_KEY` | same names, different values |
| Artifact Registry | one Docker repo in `africa-south1`, shared by both | |

Cloud SQL figures are us-central1 on-demand prices from a pricing tracker;
`db-f1-micro` is listed at about $8 in Johannesburg too. Shared-core
instances aren't covered by the Cloud SQL SLA, which is fine for staging and
a first pilot but not for schools depending on it.

**Cloud Run cost** at pilot traffic should mostly sit inside the monthly free
tier: 2 million requests, 180,000 vCPU-seconds and 360,000 GiB-seconds with
request-based billing. The free tier is calculated at Tier 1 prices, so
Johannesburg usage uses it up a bit faster. **Claude API usage is the real
variable cost** and is billed by Anthropic, not Google.

### How a change gets to schools

```
laptop ──git push──▶ GitHub main ──Actions──▶ build image ──▶ Artifact Registry
                                                  │
                     ┌────────────────────────────┴──────────────┐
                     ▼                                           ▼
   staging: migrate job → deploy API → deploy frontend    production: same steps,
            (automatic on every push to main)              on a version tag + manual approval
```

- GitHub authenticates to GCP with **Workload Identity Federation**, so no
  long-lived service-account key is stored in GitHub.
- **Migrations** run as a Cloud Run job (`alembic upgrade head`) using the
  same image, before the new API revision takes traffic. Our migrations are
  already additive. A failed migration stops the deploy.
- Cloud Run keeps previous revisions, so a bad release is **rolled back in
  one click** by sending traffic to the previous revision. A database
  migration is not rolled back that way; that's what backups are for.

### Development carries on as today

Laptop (Docker Postgres, `start-thutora.ps1`, seed accounts) → GitHub →
staging → production. Optional: a GCP browser-based dev machine, if the laptop
becomes a constraint. Work with Claude continues against the laptop copy or
GitHub.

### Code changes needed before the first deploy (Phase 1)

1. **Backend `Dockerfile`**: Python 3.12 slim, `uvicorn` on `$PORT`, non-root
   user.
2. **Config**: production reads secrets from the environment (Secret
   Manager); `CORS_ORIGINS` set per environment; the app refuses to start in
   production with dev defaults.
3. **Database connection**: Cloud SQL via its Unix socket from Cloud Run, or
   the Cloud SQL Python connector; small pool sizes (`db-f1-micro` allows few
   connections).
4. **Attachments to Cloud Storage** instead of `uploads/` on local disk.
   Cloud Run's filesystem disappears between instances, so today's code would
   lose every uploaded photo. Needs a small storage abstraction (local in
   dev, GCS in the cloud).
5. **Books**: mount the books bucket into the container (Cloud Run
   Cloud Storage volume) at `content_sources/books/`, so `BOOKS_DIR` code is
   unchanged. Run `ingest_books` once per environment as a job.
6. **Frontend API URL** from `VITE_API_BASE_URL` at build time (it's hard-coded
   to `http://localhost:8000` today).
7. **Production safety**: `seed_dev_data.py` refuses to run when
   `ENVIRONMENT=production`; schools are onboarded only with
   `scripts/provision_school.py`, run as a one-off job.
8. **Known gaps to close before real learners** (already flagged in ADR-017):
   rate-limit `POST /auth/login`; consider moving tokens from
   `sessionStorage` to httpOnly cookies.

### POPIA

- **Roles.** The school is the responsible party for its learners; Zynora is
  the **operator**. That needs a written operator agreement with each pilot
  school (POPIA s21), and an Information Officer registered for Zynora.
- **Data stays in SA** in Cloud SQL and Cloud Storage (`africa-south1`).
- **Cross-border processing (s72).** Each tutor turn sends the learner's
  question, and any attached photo or document, to Anthropic outside South
  Africa. OpenAI is also used if embeddings are enabled. Section 72 doesn't
  forbid this, but it needs a lawful ground: a data processing agreement or
  adequate protection, or consent. Already in our favour: prompts carry **no
  learner names, student numbers or school names** (checked:
  `tutor.py`, `tutor_orchestration.py`, `personalization.py` and
  `answer_marking.py` don't use them). To do: confirm Anthropic's commercial
  terms/DPA cover this use, tell schools in the operator agreement, and warn
  learners not to put their name on uploaded photos.
- **Minors.** Accounts stay school-provisioned (no self-signup), as ADR-017
  decided.
- This is not legal advice; a short review by a POPIA practitioner before the
  first real school is worth the cost.

### Money

- **Free trial**: $300 of credit for 90 days, which can't be paused or
  extended. When it ends, resources stop unless the account is upgraded to
  paid. Upgrading keeps any unused credit until day 90.
- **Google for Startups Cloud Program**: credit tiers range from about $2,000
  (pre-funded startups) to $200k–$350k for funded or AI-first startups.
  Worth applying for the Start tier now; eligibility is at Google's
  discretion.
- **Budget alerts** on both projects from day one (e.g. alerts at 50%, 90%
  and 100% of a small monthly budget), plus Anthropic usage limits.

## Phases

| Phase | What | Who |
|---|---|---|
| 0 | Push to GitHub; create the two projects; budget alerts; apply to Google for Startups | Siya (console/billing) |
| 1 | Cloud-ready code: Dockerfile, config, GCS attachments, books mount, `VITE_API_BASE_URL`, prod-safe seeding, migrate job | Claude, tested locally against Docker |
| 2 | Staging: Artifact Registry, Cloud SQL micro + pgvector, buckets, secrets, Cloud Run, Firebase Hosting, GitHub Actions with WIF; seed + ingest books | Claude writes PowerShell/`gcloud` scripts and the workflow; Siya runs the account-level steps |
| 3 | Production: own project, backups/PITR, monitoring and uptime alerts, custom domain for the frontend, manual-approval deploys | Both |
| 4 | Pilot: POPIA paperwork, `provision_school` for the school, principal onboarding, watch costs and errors | Siya + school |

## Alternatives considered

- **A single VM with Docker Compose** (closest to today, and the original
  Oracle/Coolify plan): cheapest at tiny scale, but we'd patch the OS, manage
  Postgres backups and scale by hand. It doesn't meet the "stays the main
  platform at 10M+ learners" goal.
- **GKE (Kubernetes)**: scales furthest but is far too much operational work
  for one engineer now. Cloud Run containers can move to GKE later if ever
  needed.
- **AlloyDB** instead of Cloud SQL: more performance than a pilot needs, at a
  higher floor price.
- **US region** for lower prices and built-in domain mapping: rejected,
  because learner data should stay in South Africa.

## Open items

- Domain name (e.g. `thutora.co.za`): needs registering.
- Exact Cloud SQL machine for production once real usage is known.
- Whether to add the load balancer for `api.<domain>` (fixed monthly cost)
  or stay on `*.run.app`.
- Anthropic DPA and terms confirmation for POPIA s72.
- Rate-limiting and cookie-based sessions (Phase 1 or before the pilot).
