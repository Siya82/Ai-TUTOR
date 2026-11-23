# THUTOra operations runbook

*NEW 20 Nov 2026 (deep scan H4). What to run, and what to do when something
goes wrong, once THUTOra is live on Google Cloud (ADR-033).*

## 1. Before the first school goes live

| Check | How |
|---|---|
| Production settings are safe | The API refuses to start in `ENVIRONMENT=production` with a short `JWT_SECRET_KEY`, localhost or `http://` in `CORS_ORIGINS`, `SMS_PROVIDER=console`, or no `ANTHROPIC_API_KEY` (`app/core/production.py`). A failed deploy names the setting. |
| Logs are structured | `LOG_FORMAT=json` (the Dockerfile sets it). Cloud Logging then shows severity, and Error Reporting groups tracebacks -- including frontend crashes sent to `/client-errors`. Create an Error Reporting notification to your email. |
| API explorer is off | `/docs`, `/redoc` and `/openapi.json` return 404 in production. |
| Real client addresses | The Dockerfile runs uvicorn with `--proxy-headers`. Without it every learner looks like one Google address and the per-address login limits lock out whole schools. |
| Frontend points at the API | `frontend/.env.production` sets `VITE_API_BASE_URL` (see `.env.production.example`) before `npm run build`. |
| Frontend headers | `frontend/firebase.json` sets the Content-Security-Policy and other headers. `connect-src` allows `https://*.run.app`; narrow it to the exact API address once known. |
| Retention periods set | Agree periods with the pilot schools, then set `RETENTION_CONVERSATION_DAYS`, `RETENTION_UPLOAD_DAYS`, `RETENTION_AUDIT_DAYS`. 0 keeps everything. |
| Nightly clean-up scheduled | A Cloud Run job running `python -m scripts.retention`, triggered nightly by Cloud Scheduler. Try `--dry-run` first. |
| AI budget per school | Set in ADMIN → School settings → Privacy and AI use. `python -m scripts.ai_costs` shows spend. |
| Backups on | Section 3. |
| Topic videos hosted | Upload `backend/media/topic-videos/*.mp4` to a public-read bucket folder, then `python -m scripts.topic_videos.register --base-url https://storage.googleapis.com/<bucket>/topic-videos` (ADR-049). |

## 2. Connection budget (Cloud SQL)

Each API instance holds up to `DB_POOL_SIZE + DB_MAX_OVERFLOW` connections
(default 10 + 10 = 20). Keep

    (DB_POOL_SIZE + DB_MAX_OVERFLOW) x Cloud Run max instances  <  Cloud SQL max_connections - 10

`db-f1-micro` allows about 25 connections, so staging must run **one** instance
(`--max-instances=1`). `db-g1-small` allows about 50: at most 2 instances.
Before raising max instances, move to a larger tier or lower the pool. The
tutor releases its connection during the Claude call (`release_connection`),
so 20 connections serve far more than 20 learners at once.

## 3. Backups and restore

**Production (Cloud SQL):** turn on automated daily backups (keep 14) and
point-in-time recovery when the instance is created. They're part of the
Cloud SQL price.

Restore drill -- do it once before the pilot, then each term, and write the
date in BUILD_LOG.md:

```powershell
# restore last night's backup into a NEW instance -- never over the live one
gcloud sql backups list --instance thutora-prod
gcloud sql instances clone thutora-prod thutora-restore-test --point-in-time "2026-11-20T03:00:00Z"
# point a staging API at thutora-restore-test, log in, check a learner's history, then
gcloud sql instances delete thutora-restore-test
```

**Uploaded files** live in the Cloud Storage bucket: turn on object
versioning with a 30-day noncurrent-version rule so a deleted file can be
recovered.

**Local:** `.\backup-thutora.ps1` writes `backups\thutora-<date>.dump`;
`.\backup-thutora.ps1 -Restore <file>` restores it (asks first). Never copy
production data to a laptop.

## 4. When something goes wrong

| Symptom | First check |
|---|---|
| Learners see "THUTOra is busy" / 429s | Anthropic status page; `FALLBACK_MODEL` takes over on overload. If a school's monthly AI budget ran out, ADMIN shows it; raise it or wait for the month. |
| "Too many attempts" for a whole class | Was `--proxy-headers` dropped? Otherwise clear with `DELETE FROM rate_events WHERE key LIKE 'login:%';` |
| Slow pages, timeouts | Cloud SQL connections (section 2); Cloud Run CPU. |
| A safeguarding disclosure in a conversation | Follow the school's safeguarding process. The tutor gives Childline 116 / police 10111; it never alerts anyone itself. |
| A wrong question or model answer | Teachers report it from the answer review. `python -m scripts.question_reports list`, then `hide <id>` / `fixed <id>`. |
| Suspected data breach | POPIA s22: tell the Information Regulator and the affected schools as soon as reasonably possible. `audit_events` shows who did what. |

## 4b. Support (ADR-050)

Hours: 06:00–18:00. Targets: P1 1 hour, P2 4 hours, P3 next working day,
P4 weekly.

Answer tickets in **THUTOra Console** (ADR-051) → Tickets. The scripts still
work as a fallback when the Console is down:

```powershell
python -m scripts.support list            # waiting for us, most urgent first
python -m scripts.support show 42
python -m scripts.support reply 42 "..."  # add --resolve when it's done
```

- A **safeguarding** ticket: check that the school has followed its own
  process, then reply the same day. THUTOra never contacts a learner or
  parent directly.
- A **data/privacy** ticket may be a POPIA breach: follow section 4
  ("Suspected data breach").
- Set `SMTP_*` in production so new tickets reach support@zynoratech.co.za.
  Without it, they only appear in the logs.

## 4c. THUTOra Console (ADR-051)

Zynora's internal tool: tickets, school registrations, setting up schools,
principals, officials, an audit log, and Console staff. It's a separate
website (`console/`) that uses the same API under `/console`.

**First director** (once per environment), from `backend` with the venv active:

```powershell
python -m scripts.console_staff create --email siya@zynoratech.co.za --name "Siya Zondi" --role director
```

Sign in at the Console with the printed password, scan the QR code with an
authenticator app, and choose your own password. Add everyone else in the
Console under **Console staff**. Keep **two directors**, so one can reset
the other.

**Locked out** (lost phone, forgotten password, every director locked out):

```powershell
python -m scripts.console_staff reset-authenticator --email siya@zynoratech.co.za
python -m scripts.console_staff reset-password --email siya@zynoratech.co.za
```

**Production:**
- Host it as its own Firebase site (`console/firebase.json` names the site
  `thutora-console`), e.g. `console.thutora.co.za`. Build it with
  `console/.env.production` pointing at the API.
- Set `CONSOLE_ORIGINS=["https://console.thutora.co.za"]` on the API. In
  production `/console` answers only that address; the API won't start if
  it's missing, is http, or is a school app address.
- `CONSOLE_ENABLED=false` switches every `/console` endpoint off (for
  example during an incident).
- Optional, stronger: allow the Console address only from Zynora's office
  IP (Cloud Armor or Firebase Hosting rules).

Sessions last 30 minutes. Every action is in Console → Audit log, and
actions on a school also show in that school's ADMIN → Activity as
"THUTOra support".

## 5. Releasing

1. CI green (tests, lint, build, `pip-audit`, `npm audit`).
2. Cloud Run job: `alembic upgrade head`.
3. Deploy the API image, then the frontend, then the Console
   (`firebase deploy --only hosting:thutora-console` from `console/`).
4. Log in as each role on staging before promoting to production.
