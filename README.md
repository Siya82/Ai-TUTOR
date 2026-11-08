# AI CAPS Tutor — Pilot ("Zynora" scope)

An AI-powered tutor for **CAPS Grade 10 Mathematics** — deliberately
scoped to one subject, done exceptionally well, rather than a broader
platform done shallowly. See
[`docs/ADR-006-maths-only-scope.md`](docs/ADR-006-maths-only-scope.md)
for the reasoning: Grade 10 Maths is the transition point from arithmetic
to abstraction, and underpins success in Grade 11/12, Physical Sciences,
Engineering, Computer Science, Data Science, and Economics — so getting
this one subject right has outsized leverage even before expanding.

## Why this scope

Started as a two-subject pilot (Maths + Physical Science); narrowed to
Maths-only after a strategy review argued for depth over breadth. See
[`docs/ADR-001-tech-stack.md`](docs/ADR-001-tech-stack.md) and
[`docs/ADR-006-maths-only-scope.md`](docs/ADR-006-maths-only-scope.md)
for the reasoning, and [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md) for a
chronological record of what's been built and why. Physical Science work
already built (labs engine, video resources) is paused, not discarded —
the underlying patterns are subject-agnostic.

## Repository structure

```
ai-caps-tutor/
├── backend/          FastAPI + PostgreSQL/pgvector API
│   ├── app/
│   │   ├── core/      config, database session
│   │   ├── models/    SQLAlchemy models (schema)
│   │   ├── routers/   API endpoints (built incrementally)
│   │   └── services/  business logic (tutor, diagnosis, personalization,
│   │                   risk, labs)
│   └── tests/
├── frontend/          React + Vite PWA (not yet started)
├── scripts/           CAPS content ingestion pipeline (not yet started)
└── docs/
    ├── ADR-001-tech-stack.md   architecture decisions
    └── BUILD_LOG.md            chronological build history
```

## Tech stack

FastAPI · PostgreSQL + pgvector · Anthropic Claude API · dbt (SQL
transformations only — see ADR-009) · React/Vite · Oracle Cloud Free Tier
+ Coolify

## Local setup (backend)

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY and DATABASE_URL
uvicorn app.main:app --reload
```

Then check `http://localhost:8000/health` — you should see
`{"status": "ok", "environment": "development"}` once Postgres is running
and reachable.

## Current status (as last directly verified, 26 Aug 2026 — see REBUILD_SPEC.md for everything built after this)

Backend skeleton with core schema (`Subject`, `Topic`, `ContentChunk`,
`Learner`, `Question`, `Attempt`) is built and verified (imports cleanly,
app boots). All 12 CAPS Grade 10 Pure Mathematics topics are seeded with
diagnostic questions and prerequisite chains. MathGuard self-verification
and recursive root-cause diagnosis are both live. A teacher dashboard API
exists. See `docs/ADR-011-protected-differentiators.md` for the fullest
picture as of this snapshot.
