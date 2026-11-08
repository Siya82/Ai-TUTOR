# Build Log

Chronological record of what was built, when, and why. Each entry should be
added at the time the work happens, not reconstructed later.

---

## 2026-07-31 — Project scaffolding

**Goal:** Stand up the repository structure and documentation framework
before any feature code, so every subsequent decision is captured.

**Done:**
- Created top-level structure: `backend/`, `frontend/`, `scripts/`, `docs/`
- Established `docs/ADR-NNN-*.md` convention for architecture decisions
- Established this build log for chronological progress tracking
- Locked tech stack: FastAPI + PostgreSQL/pgvector + Claude API +
  Apache Hop/dbt + React/Vite + Oracle Cloud/Coolify (see ADR-001)
- Scoped pilot to Grade 10, Pure Mathematics + Physical Science

**Not done yet (next steps):**
- Database schema for learners, subjects, topics, questions, attempts
- FastAPI app skeleton with health check + config loading
- CAPS content sourcing checklist (Step 1 of the roadmap)
- Content ingestion pipeline (chunk → embed → pgvector)

**Decisions made:**
- Two subjects from day one (not one subject then a second later) since
  Pure Maths and Physical Science share enough foundational concepts
  (algebra, functions, graphs, units) that building shared infrastructure
  for both now is cheaper than retrofitting later.

---

## 2026-07-31 — Backend skeleton + core schema

**Goal:** A booting FastAPI app backed by a real (if not yet populated)
database schema, verified end-to-end before moving on.

**Done:**
- `backend/app/models/__init__.py` — six SQLAlchemy models: `Subject`,
  `Topic`, `ContentChunk`, `Learner`, `Question`, `Attempt`
- `backend/app/core/config.py` — Pydantic settings loaded from `.env`
- `backend/app/core/database.py` — async SQLAlchemy engine/session
  (asyncpg), so DB calls don't block while the API is also awaiting
  Claude API calls in the same request
- `backend/app/main.py` — FastAPI app with `/health` endpoint that
  round-trips a real DB query
- `backend/requirements.txt`, `backend/.env.example`
- **Verified:** dependencies install cleanly in a fresh venv; models and
  app import without error; route table confirmed (`/health`, `/docs`,
  `/openapi.json`)

**Schema design decisions:**
- `Attempt` is the single source of truth both the diagnostic assessment
  and adaptive practice loop write to — mastery is always derived from
  attempt history, never stored as a separate mutable "mastery score"
  field, so it can't drift out of sync.
- `Question.is_diagnostic` / `is_ai_generated` flags keep the curated
  diagnostic bank (Step 3 of the roadmap) and AI-generated practice
  questions (Step 5) in one table without risk of mixing them up.
- `ContentChunk.embedding` uses `pgvector`'s `Vector(1536)` type
  (matches typical embedding dimensionality) — actual embedding model
  choice is deferred to the content-ingestion step.

**Not done yet (next steps):**
- Alembic migration to actually create these tables in a running Postgres
  instance (schema exists in code, not yet applied to a database)
- CAPS content sourcing for Grade 10 Pure Maths + Physical Science
- Content ingestion pipeline (chunk → embed → `ContentChunk` rows)

---

## 2026-07-31 — Personalization: presentation preference + adaptive pace

**Goal:** Let the tutor adapt to how a learner is comfortable being taught
and how much scaffolding they currently need, without diagnosing learners
into fixed "learning style" labels (see ADR-002 for why that approach was
rejected).

**Done:**
- `docs/ADR-002-personalization.md` — reasoning for presentation
  preference (learner-chosen, changeable) + adaptive pace (computed from
  performance) instead of a VARK-style diagnosed learning-style label
- `Learner.preferred_modality` column added (`visual` / `practical` /
  `auditory` / `balanced`) — learner-editable preference, not diagnosed
- `app/services/personalization.py`:
  - `compute_pace_tier()` — derives `needs_support` / `on_pace` /
    `ready_for_extension` from a learner's last 14 days of attempts on a
    topic (accuracy-based; defaults to `on_pace` if fewer than 3 recent
    attempts exist, so a new learner is never told they're behind before
    they've had a fair chance)
  - `build_personalization_instructions()` — turns modality + pace tier
    into a system-prompt block for the tutor/practice-generation Claude
    calls, kept separate from the core CAPS-grounding prompt so it can be
    audited/tested independently
- **Verified with test scenarios:** struggling learner (2/5 correct) →
  `needs_support`; strong learner (6/6 correct) → `ready_for_extension`;
  new learner with only 2 attempts → defaults to `on_pace` rather than
  guessing; attempts older than the 14-day window are correctly excluded
  from the calculation

**Bug caught during verification (worth recording):** initially "fixed" a
`datetime.utcnow()` deprecation warning by switching the pace calculation
to timezone-aware datetimes. This broke the comparison against
`Attempt.created_at`, which still uses the naive `datetime.utcnow` default
from the schema — reverted immediately rather than shipping it. Real fix
is to migrate the whole schema to timezone-aware timestamps in one pass,
not patch one function at a time. Tracked as a follow-up, not fixed here.

**Deliberately deferred:**
- Response-time as a second pace signal (currently accuracy-only) — needs
  the frontend to actually capture and send timing data first
- The modality instructions (visual/practical/auditory prompt text) are a
  first draft — should be refined once we see real tutor output against
  them, not treated as final copy

**Not done yet (next steps):**
- Wire `build_personalization_instructions()` into an actual `/tutor`
  endpoint (doesn't exist yet — this service is built ahead of the
  endpoint deliberately, so personalization isn't retrofitted later)
- `PATCH /learners/{id}` endpoint so a learner can actually change
  `preferred_modality` from the frontend
- Timezone-aware datetime migration across the schema (see bug note above)

---

## 2026-07-31 — Tutor pedagogy (explain every transformation) + early-warning risk model

**Goal:** Two requirements from the product owner: (1) the tutor must
explain *why* every step is valid, not just produce answers, anchored by
the `2x + 5 = 15` example; (2) predictive early-warning of at-risk
learners, months before failure, for education-department value.

**Done — tutor pedagogy:**
- `docs/ADR-003-explain-every-transformation.md`
- `TutorSession` + `TutorMessage` models — persisted multi-turn
  conversations so a "why?" follow-up has full prior context
- `backend/app/services/tutor.py`:
  - `build_tutor_system_prompt()` — non-negotiable "explain why" rule,
    anchored by the exact `2x + 5 = 15` worked example, RAG grounding
    placeholder, personalization block, scope discipline
  - `TutorClient` — thin Anthropic API wrapper, mockable, not called live
    in this build step (no API key configured in this environment) but
    prompt construction fully verified
- **Verified:** prompt correctly contains the worked example and "WHY"
  emphasis; 8 database tables now import and register cleanly together

**Done — early-warning risk model:**
- `docs/ADR-004-risk-model.md` — records the honest decision to build an
  interpretable rule-based v1, NOT a trained ML model, because there is
  no historical outcome data yet to train one on credibly. Framed as the
  data-generation phase for a real predictive model later.
- `backend/app/services/risk.py` — `assess_risk()` combining three signals:
  declining accuracy trend, weak prerequisite-topic mastery (the actual
  "before it happens" mechanism — flags risk on a topic before the
  learner has attempted it, using the curriculum's prerequisite structure),
  and disengagement
- **Verified with 5 scenarios:** healthy learner → low; declining trend
  only → medium; weak prerequisite with topic not yet attempted → medium
  (confirms the predictive-before-attempting mechanism works); trend +
  prerequisite combined → high; disengagement after prior activity →
  medium

**Bug caught and fixed during this step:** a `str_replace` edit adding
`TutorSession`/`TutorMessage` to the models file accidentally deleted the
`class Attempt(Base):` declaration line, silently merging `Attempt`'s
body into `TutorMessage`. Caught immediately because the verification
step checks for exactly 8 distinct table names, not just "does it
import" — it imported fine even in the broken state, it just had the
wrong table count. Fixed and re-verified. Recorded here as a reminder
that "it imports" is not sufficient verification for schema changes;
checking actual table/attribute counts is what caught this.

**Deliberately deferred:**
- Risk model thresholds (15% accuracy drop, 10-day inactivity, 60%
  prerequisite mastery cutoff) are initial estimates, not calibrated
  against real outcomes — expect to tune once pilot data exists
- `TutorClient` not exercised against the live Anthropic API yet — needs
  a real API key and a `/tutor` endpoint wired up

**Not done yet (next steps):**
- `/tutor` POST endpoint wiring `TutorClient` + session persistence together
- `/risk/{learner_id}` endpoint exposing `assess_risk()` results
- Content ingestion pipeline (RAG grounding is still a placeholder string)
- Database migration + real Postgres instance

---

## 2026-07-31 — Video resources + virtual labs (deterministic, not AI-computed)

**Goal:** Video content and interactive "virtual lab" experiences (e.g.
mixing substances and getting real measured results), on mobile.

**Research first:** confirmed via web search that free, CAPS-aligned video
content already exists at scale (Mindset Learn, Siyavula, Khan Academy),
and that South African Physical Sciences teachers already use PhET
Interactive Simulations (University of Colorado) for lab-style interactive
content. This changed the build plan — see ADR-005.

**Done:**
- `docs/ADR-005-labs-and-resources.md` — records the decision to (1)
  curate existing video rather than build a video pipeline, (2) embed
  existing validated PhET simulations where they cover a CAPS topic
  ("Tier 1") rather than rebuild them, (3) build our own interactivity
  only for the fixed, official CAPS-prescribed practical list ("Tier 2"),
  with results always computed by deterministic code — never by the LLM.
  Also explicitly records **why** an open "mix any element, any
  measurement" sandbox was rejected: accurate general chemistry
  simulation is a hard scientific engineering problem, and a smaller
  unvalidated version of it would silently be wrong outside whatever
  narrow set of cases it happened to be built for — worse than not
  having the feature, in a subject where correctness matters.
- Schema additions: `VideoResource` (curated external video, linked to a
  topic), `Practical` (a CAPS-prescribed practical, with a
  `calculation_key` mapping to real code and an optional
  `phet_simulation_url` for Tier 1 cases), `PracticalRun` (a learner's
  inputs + the code-computed outputs)
- `backend/app/services/labs.py` — deterministic calculation engine,
  registry pattern (`PRACTICAL_CALCULATIONS`) for adding practicals.
  First implemented practical: **Mg + HCl reaction** (CAPS Grade 10
  prescribed practical — metal + dilute acid, measuring gas produced).
  Computes moles of each reactant, correctly identifies the limiting
  reagent, and computes volume of hydrogen gas produced from real
  stoichiometry (Mg + 2HCl -> MgCl2 + H2).
- **Verified:** two limiting-reagent scenarios (excess acid → Mg
  limiting; excess Mg → HCl limiting) both correctly identified; output
  volume cross-checked by hand calculation (expected ~0.922 dm³, got
  0.922 dm³); negative/invalid input correctly rejected; all 11 database
  tables still import and register together cleanly

**Explicitly flagged, not swept under the rug:** the molar mass and molar
volume constants used (`MOLAR_MASS_MAGNESIUM_G_PER_MOL`,
`MOLAR_VOLUME_GAS_DM3_PER_MOL`) are standard textbook values, not yet
cross-checked against the actual current CAPS/DBE Physical Sciences Data
Booklet — the exact reference sheet used in NSC exams. This is called out
directly in the module docstring and constant comments. **Must be
verified before any pilot use** — a subtly wrong constant in a chemistry
tool is worse than not having the tool at all.

**Deliberately deferred:**
- Only one practical implemented so far — the registry pattern makes
  adding more straightforward once the CAPS prescribed practical list is
  gathered in full
- No PhET simulations actually linked yet — `phet_simulation_url` field
  exists but is unpopulated
- No frontend lab UI — this is backend calculation logic only

**Not done yet (next steps):**
- Gather the full official CAPS Grade 10 Physical Sciences prescribed
  practical list and cross-check all constants against the Data Booklet
- `/practicals/{id}/run` endpoint wiring learner inputs → calculation →
  persisted `PracticalRun` → LLM narration of the (already-correct) result
- Curate and populate `VideoResource` rows against the topic list
- Mobile-friendly frontend for practicals (sliders/inputs for mass,
  volume, concentration — works on any device, no lab hardware needed)

---

## 2026-07-31 — Verified lab constants against the real official NSC Data Sheet

**Goal:** Close the "must verify before pilot use" flag from the previous
build step — don't leave a chemistry constant unverified.

**Done:**
- Fetched the actual Siyavula Grade 10 Physical Sciences textbook (linked
  by the product owner) and confirmed magnesium's molar mass (24,3 g/mol)
  matches its periodic table exactly.
- Searched for and cross-checked against four independent official NSC
  Physical Sciences Paper 2 Data Sheets (2016, 2018, plus others) —
  confirmed molar gas volume at STP is 22,4 dm³/mol, matching the code.
- **Caught a real gap in the process of verifying:** one of the released
  NSC exam papers explicitly instructs candidates to use 24 dm³/mol (not
  22,4) for a room-temperature calculation. STP and RTP are genuinely
  different physical conditions with different correct molar volumes —
  the original code silently assumed STP for everything, which would
  have been wrong for any practical framed at room temperature.
- **Fixed:** `calculate_magnesium_hcl_reaction()` now takes an explicit
  `GasCondition` (STP or RTP) parameter — no silent default hidden inside
  the calculation; callers must state which condition the practical
  assumes. Defaults to STP if unspecified, matching the Data Sheet's
  primary listed value.
- **Verified:** same reaction inputs correctly produce the same moles of
  H2 but different gas volumes under STP vs RTP (0.922 dm³ vs 0.988 dm³);
  all previous limiting-reagent test cases still pass unchanged.

**Why this matters as a process note, not just a code note:** the
previous build step's constants were individually correct but the
*framing* was incomplete — "the molar volume" isn't a single number,
it depends on stated conditions. Checking a constant against a source
isn't enough if the source itself specifies more than one value for
different conditions; this is caught by working through actual exam
material, not just a textbook data table.

**Not done yet:** still only one practical implemented; the DBE Data
Sheet PDF itself (not just search snippets of it) hasn't been directly
sourced yet — worth doing before adding more practicals with more
constants, to check the primary document rather than continuing to rely
on search excerpts of past exam papers.

---

## 2026-07-31 — Scope narrowed to Grade 10 Maths only + root-cause diagnosis

**Goal:** Incorporate a strategy document ("Zynora") that argued for
narrowing to one subject done exceptionally well, and build the one
genuinely new piece of engineering value in it: recursive root-cause
diagnosis through the prerequisite chain.

**Done — scope decision:**
- `docs/ADR-006-maths-only-scope.md` — pilot narrowed from Maths +
  Physical Science to **Maths only**. Physical Science work (labs engine,
  video resources) explicitly marked as paused, not discarded — the
  underlying patterns (deterministic calculation registry, curated
  resource linking) are subject-agnostic and can be re-enabled later.
- `README.md` updated to reflect the new scope and reference both ADRs.

**Done — root-cause diagnosis:**
- `docs/ADR-007-root-cause-diagnosis.md` — records why this differs from
  the existing per-topic mastery check (`assess_risk` in ADR-004): this
  answers "where should teaching actually start," not "how is the
  learner doing at this topic."
- `backend/app/services/diagnosis.py` — `diagnose_root_gap()` walks a
  resolved prerequisite chain (via `Topic.prerequisite_id`), checking
  mastery at each step, and returns the deepest topic with unconfirmed or
  insufficient mastery as the recommended teaching start point — with a
  full human-readable reasoning trace, not just a final answer.
- **Verified with 4 scenarios**, including the exact example from the
  source document (learner weak on Factorisation, strong on
  Multiplication, asking about Quadratic Equations → correctly diagnosed
  to start at Factorisation, correctly stops there rather than walking
  further back to Multiplication which is solid). Also verified: solid
  prerequisite mastery → teach the requested topic directly; no attempt
  history anywhere → conservatively walks to the root of the chain rather
  than assuming competence; a single correct attempt is treated as
  unconfirmed, not as proof of mastery.
- Full integration re-verified: all 5 services (personalization, tutor,
  risk, labs, diagnosis) and the FastAPI app still import and boot
  together cleanly.

**Explicitly deferred (noted, not built):** the source document's "AI
Personas" (Teacher/Friend/Engineer/Visual/Exam Coach mode names) are
functionally the same mechanism as the existing `preferred_modality`
personalization (ADR-002) — just better UX naming. Worth adopting the
naming later; not rebuilt now since it's a labeling change, not new
capability, and lower priority than the diagnosis engine.

**Not done yet (next steps):**
- A function to actually resolve the prerequisite chain from the database
  (`diagnose_root_gap` takes an already-ordered chain — the DB traversal
  that produces it doesn't exist yet)
- Wire diagnosis into the tutor flow: when a learner asks about a topic,
  run `diagnose_root_gap` before generating the first tutor response
- `/tutor`, `/practicals/run`, and now `/diagnose` endpoints all still
  need to be built — five services now exist with zero HTTP endpoints
  exposing them; this is becoming the highest-priority next step

---

## 2026-07-31 — First real HTTP endpoint: POST /tutor/message

**Goal:** Turn the five existing services into something actually
callable. Started with `/tutor/message`, wired to run root-cause
diagnosis before generating any response, per the plan agreed at the end
of the last build step.

**Done:**
- `backend/app/services/tutor_orchestration.py` — pure function
  `prepare_tutor_turn()` that runs diagnosis (ADR-007) first, then builds
  personalization (ADR-002) and the full tutor system prompt (ADR-003)
  grounded on whatever topic the diagnosis says to actually teach, which
  may differ from what the learner asked. When it does differ, the prompt
  gets an explicit "diagnosis note" instructing the tutor to explain the
  redirect to the learner in one encouraging sentence before teaching.
  Kept DB-free specifically so this decision logic is unit-testable.
- **Verified with 3 scenarios:** weak prerequisite → redirects teaching
  target, prompt contains diagnosis note and correct modality instructions;
  solid prerequisites → teaches the requested topic directly, no diagnosis
  clutter in the prompt; invalid/legacy `preferred_modality` value on the
  learner record → falls back to `balanced` instead of crashing.
- `backend/app/routers/tutor.py` — `POST /tutor/message`:
  - Fetches learner, topic, subject from the database
  - Resolves the prerequisite chain by walking `Topic.prerequisite_id`
    (cycle/missing-data guarded, capped at depth 10)
  - Gathers the learner's attempt history across the topic and its full
    prerequisite chain (joined through `Question.topic_id`, since
    `Attempt` doesn't carry topic directly)
  - Calls `prepare_tutor_turn()`, then either continues an existing
    `TutorSession` (loading prior `TutorMessage` history for context) or
    creates a new one
  - Calls `TutorClient`, persists both the user message and the reply,
    commits, returns the reply plus which topic was actually taught and
    the full diagnosis reasoning trace
  - **Checks `ANTHROPIC_API_KEY` is configured before touching the
    database at all** — fails fast with a clear 503, not a confusing
    partial failure or a 500 after a wasted DB round-trip
- Registered the router in `app/main.py`; removed the now-stale
  "routers go here" placeholder comment

**Verified (with real tool calls, not just code review):**
- App boots with the router mounted; `POST /tutor/message` appears in
  the route table alongside `/health`
- Request/response Pydantic schemas validate correctly, including the
  optional `session_id` field (present = continue a session, absent =
  start one) and correctly reject a request missing a required field
- Used FastAPI's `TestClient` to actually call the endpoint (not just
  import it) — confirmed it returns a clean `503` with a clear message
  when `ANTHROPIC_API_KEY` isn't configured, and confirmed this check
  happens *before* any database dependency is invoked

**Explicitly NOT verified (flagged, not hidden):** no live Postgres
instance exists yet, so the actual DB query paths (prerequisite chain
resolution, attempt grouping, session persistence) have been reviewed and
reasoned through but not run against a real database. No Anthropic API
key is configured in this environment, so `TutorClient.ask()` has never
been exercised against the live API — only its construction and the
prompt it receives have been verified. Both need a real environment
(database + API key) for genuine end-to-end verification — that's the
natural next integration step once those exist.

**Not done yet (next steps):**
- Provision a real Postgres instance + run a migration, so the DB query
  paths in this endpoint can finally be tested for real, not just
  reasoned through
- Add a real `ANTHROPIC_API_KEY` and do a first genuine live tutor call
  — this is the real test of whether the "explain every transformation"
  prompt (ADR-003) actually produces the quality of teaching intended
- `/practicals/{id}/run` and `/risk/{learner_id}` endpoints, following
  the same pattern established here (pure orchestration layer + thin
  DB-aware router)
- `PATCH /learners/{id}` so `preferred_modality` is actually settable

---

## 2026-08-02 — Zynora brand design tokens

**Goal:** Product owner confirmed the project's company name (Zynora
Technologies) and shared the official logo, asking for a CSS color scheme
derived from it.

**Done:**
- Sampled actual pixel RGB values from the uploaded logo (not eyeballed):
  background, wordmark, and three independent cyan accent points, cross-
  checked against each other to confirm one consistent brand accent color
  rather than several similar ones (see ADR-008 for the full method and
  values).
- `docs/ADR-008-brand-design-tokens.md`
- `frontend/src/styles/tokens.css` — CSS custom properties: three
  measured brand tokens (`--zynora-black`, `--zynora-white`,
  `--zynora-cyan`), standard-practice derived surface/text levels clearly
  marked as NOT sampled from the logo, and semantic aliases
  (`--color-background`, `--color-accent`, etc.) for components to
  actually use.
- `demo/tokens-demo.html` — visual demo (wordmark, swatches, a card
  matching the tutor UI's likely shape, a glowing button) to check the
  tokens render as intended.

**Not verified:** no headless browser in this environment, so the demo
has not been screenshotted/visually confirmed here — needs to be opened
in a real browser before relying on it. Also flagged: these are sampled
from a PNG export of the logo, not an authoritative brand guideline
document — if Zynora has an official brand book/Figma file with exact
specified hex values, that should override these.

**Not done yet (next steps):**
- Open `demo/tokens-demo.html` in an actual browser to visually confirm
- Typography wasn't addressed — the wordmark uses a geometric sans with
  wide letter-spacing; worth deciding a body/display type pairing
  alongside the color system, not assumed here since it wasn't asked for
- No frontend framework/build tooling exists yet (`frontend/` is still
  just this one CSS file) — React/Vite scaffolding is still a future step

---

## 2026-08-02 — Removed Apache Hop from the stack

**Goal:** Product owner asked to drop Apache Hop and use dbt only.

**Done:**
- `docs/ADR-009-remove-apache-hop.md` — records the scope clarification
  that matters here: Hop and dbt weren't doing the same job. Hop was
  handling PDF extraction + embedding-API calls + loading into pgvector;
  dbt only does SQL transformations on data already in Postgres. Removing
  Hop means content ingestion becomes a plain Python script
  (`scripts/ingest_content.py`, not yet built), not a Hop-to-dbt
  substitution. dbt's actual scope narrows to what it always did well:
  transformations on already-loaded data (e.g. future mastery-rollup
  views for the teacher dashboard).
- Updated `README.md` tech stack line.

**Why this is a good simplification, not just a requested change:** one
fewer service to run on Oracle Cloud Free Tier for a solo-maintained
pilot — Hop's runtime overhead wasn't earning its keep for what is, at
pilot scale, a fairly small PDF-ingestion task.

**Not done yet (next steps):**
- `scripts/ingest_content.py` — the actual Python ingestion script (PDF
  extract → chunk → embed → load into `content_chunks`) still needs to
  be built; this ADR only corrects the plan, not the missing
  implementation
- No dbt models exist yet either — both are blocked on CAPS content
  sourcing, which remains an open task

---

## 2026-08-02 — Local dev setup guide, verified end-to-end for real

**Goal:** A guide for running this locally — not written from assumption,
but actually run against a real PostgreSQL 16 + pgvector instance in this
build session first, so every step is verified rather than described.

**Done:**
- Installed real PostgreSQL 16 + `postgresql-16-pgvector` in this build
  environment (confirmed via `apt`), started it, created the `vector`
  extension, confirmed with `\dx`.
- Initialized Alembic (`migrations/`), wired `env.py` to import
  `Base.metadata` from `app.models` and to derive its connection string
  from `app.core.config.settings` (swapping `+asyncpg` for `+psycopg2`
  since migrations run sync, the app runs async) — one `DATABASE_URL`,
  not two divergent connection strings to keep in sync.
- Ran `alembic revision --autogenerate` — correctly detected all 11
  tables from the models.
- **Caught and fixed two real bugs** on first migration attempt (not
  hidden — documented in `docs/LOCAL_SETUP.md` directly):
  1. The autogenerated migration referenced `pgvector.sqlalchemy.vector.
     VECTOR` without importing `pgvector` — `NameError` on first run.
     Added the import.
  2. The migration had no `CREATE EXTENSION IF NOT EXISTS vector`
     statement — it would only have worked because the extension was
     already manually enabled on this dev database. Added the statement
     to the migration itself so it works on a genuinely fresh database.
  3. **Verified the fix for real**: dropped the database entirely,
     recreated it fresh (no manual extension setup), re-ran
     `alembic upgrade head` — succeeded cleanly this time.
- Confirmed all 12 tables exist post-migration (11 application tables +
  Alembic's tracking table) via `psql \dt`.
- **Booted the actual FastAPI app against this live database** and hit
  `/health` with `curl` — first genuine end-to-end verification of the
  whole stack (app → SQLAlchemy → asyncpg → real Postgres → pgvector),
  not a mocked or reasoned-through check. Confirmed `200 OK` with a real
  `SELECT 1` round-trip in the server logs.
- `docker-compose.yml` — `pgvector/pgvector:pg16` image, so local setup
  doesn't require compiling pgvector from source (painful on Windows
  specifically, which matters since local dev may be on Windows).
- `docs/LOCAL_SETUP.md` — the actual guide, built from what was just
  verified, including both caught bugs documented as context for the
  reader rather than silently fixed and unmentioned.

**Explicitly noted as unverified:** the Docker Compose path itself wasn't
tested in this session (no Docker daemon available in this sandboxed
environment) — the manual `apt`-based Postgres setup was used instead to
verify the migration and app. The compose file is a standard, well-known
image configuration, but should be confirmed working on your actual
machine as the true first real-world test of that specific path.

**Not done yet (next steps):**
- A seed script for at least one `Subject`/`Topic` chain/`Learner`, so
  `/tutor/message` has something to actually respond about once run
  locally — right now every foreign key would 404
- The CAPS content ingestion script (unblocked now that a working local
  DB setup exists, but still not built)

---

## 2026-08-02 — Windows PowerShell install script

**Goal:** Automate the software installation step from `LOCAL_SETUP.md`
via PowerShell/winget, since local dev is likely on Windows.

**Done:**
- `scripts/windows-setup.ps1` — installs Git, Python 3.12, VS Code, and
  Docker Desktop via `winget`; checks/enables WSL2 (Docker Desktop's
  dependency); installs three VS Code extensions if `code` is already on
  PATH, prints manual instructions if not.
- Updated `docs/LOCAL_SETUP.md` to reference it, with explicit limits
  called out: Docker Desktop's first-run license/WSL2 confirmation isn't
  scriptable (GUI-only, on first launch), and getting an Anthropic API
  key is inherently manual.

**Explicitly NOT verified — flagged plainly, not glossed over:** no
Windows environment or PowerShell interpreter was available in this
build session to actually run this script. It's written correctly
against known `winget` package IDs and standard patterns, but this is
the first script in the whole project that hasn't been executed and
proven to work before being handed over — every other deliverable in
this build log was run for real. Real-world testing on an actual Windows
machine is the genuine next step for this file specifically.

**Not done yet (next steps):**
- Run `windows-setup.ps1` on a real Windows machine and fix whatever
  breaks — first true test
- Seed script for `Subject`/`Topic`/`Learner` rows (still open from the
  previous build step)
- CAPS content ingestion script (still open)

---

## 2026-08-03 — First real-world confirmation: Docker steps worked exactly as documented

**Goal:** Nothing new built — recording that the Docker database setup
guide was run on a real Windows machine (product owner's actual dev
environment) for the first time, and confirming what happened.

**Confirmed working, on a real machine, not this sandbox:**
- `docker compose up -d` — pulled the image, created network/volume,
  started the container, exactly as documented
- `docker compose ps` — showed the `db` service `Up`, port mapping
  `0.0.0.0:5432->5432/tcp` as expected
- `docker compose logs db` — clean Postgres 16.14 startup, no errors
- The `\dx` verification command — correctly showed only `plpgsql`, NOT
  `vector` yet. This matches exactly what `LOCAL_SETUP.md` said would
  happen at this stage (extension is created by the Alembic migration,
  not container startup) — a good sign the documentation's predictions
  are accurate, not just its happy-path instructions.

**Bug found and fixed in the docs themselves** (not the code): a `str_
replace` edit to add the PowerShell execution-policy note left a
dangling, incorrectly-paired code fence in `LOCAL_SETUP.md`'s backend
setup section. Caught by re-viewing the file after editing — same
discipline applied to markdown as to code changes in this project, not
just assumed correct because the edit tool reported success. Fixed, and
also corrected `python3` (Mac/Linux) vs `python` (Windows) in the same
pass, plus added the PowerShell execution-policy gotcha
(`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`)
proactively since the product owner is confirmed to be on PowerShell.

**Not done yet:** backend setup (venv, dependencies, `.env`, migration)
hasn't been run on the real machine yet — that's the natural next step,
and will be the first real-world test of the Alembic migration + FastAPI
boot sequence outside this sandbox.

---

## 2026-08-03 — One-command dev startup script

**Goal:** Product owner asked for a single script to run everything at
startup, after working through the manual steps by hand.

**Done:**
- `scripts/start-dev.ps1` — starts Docker, polls `pg_isready` in a retry
  loop (up to 60s) rather than assuming the container being "Up" means
  Postgres is actually ready to accept connections, creates the venv and
  installs dependencies on first run only, prompts to fill in `.env` if
  missing (opens Notepad directly, waits for confirmation before
  continuing), runs `alembic upgrade head` (safe to run every time —
  Alembic only applies pending migrations), then starts `uvicorn`.
  Supports `-SkipDocker` and `-SkipInstall` flags for faster subsequent
  runs.
- Updated `docs/LOCAL_SETUP.md` to reference it as the day-to-day
  shortcut once the manual setup has been done once.

**Sanity-checked, not executed:** no PowerShell interpreter available in
this sandbox, so — same as `windows-setup.ps1` — this could not be run
and confirmed. Did verify brace/paren balance and structural correctness
programmatically before handing it over, but that's a syntax sanity
check, not proof it runs correctly end-to-end.

**Not done yet (next steps):**
- Run this on the real machine — first true test
- Frontend startup isn't included yet (no frontend framework exists to
  start — see earlier build log entries)

---

## 2026-08-02 — Detailed Docker database walkthrough

**Goal:** Expand the terse "docker compose up -d" step into real
step-by-step guidance, since this is the part of local setup most likely
to trip someone up on first attempt (Docker Desktop not started, port
conflicts with a native Postgres install, etc.).

**Done:**
- Rewrote `docs/LOCAL_SETUP.md` section 3 into 7 explicit steps: confirm
  Docker Desktop is actually running (not just installed), start the
  container, confirm it's up, verify pgvector is present (and note it's
  expected to be absent until the migration runs — avoiding a false
  alarm), connect a GUI tool if preferred.
- Added a day-to-day command reference table (`up -d` / `down` / `down -v`
  / `logs` / `ps`) and a troubleshooting section covering the three most
  likely real failure modes: Docker daemon not running, port 5432
  already taken by a native Postgres service, and the container reporting
  "Up" before Postgres inside it has actually finished starting.

**Confirmed cross-platform note:** the `$(docker compose ps -q db)`
command substitution used in the verification command works identically
in PowerShell and bash — no Windows-specific syntax change needed there.

**Not verified:** same caveat as the rest of the Docker path — no Docker
daemon available in this sandbox to actually run `docker compose up -d`
and confirm these exact steps end-to-end. The underlying Postgres +
pgvector + migration behavior IS verified (see the 2026-08-02 entry
above, done via a directly-installed Postgres) — what's unverified here
specifically is the Docker container orchestration layer on top of it.

---

## 2026-11-08 -- Backend rebuilt and booted locally (REBUILD_SPEC.md step 1)

**Goal:** After the laptop loss and recovery documented in REBUILD_SPEC.md,
get the recovered backend core actually booting again against a fresh
local Postgres + pgvector, on the new laptop -- which, going forward, is
the primary machine all projects run from (not the old HP laptop).

**Done:**
- Filled in the two modules that were referenced but never recovered
  verbatim: a step-2 placeholder `app/routers/tutor.py` (so `app.main`
  imports cleanly -- the real tutor logic is next, not this entry), and
  `app/schemas/dashboard.py` (reconstructed from the exact dict shapes
  `services/dashboard.py` and `services/risk_assessment.py` already
  return, since the schemas file itself never made it into the recovery
  package).
- Added the missing `__init__.py` files for app/app.routers/app.services/
  app.core -- never recovered, not previously noticed since nothing had
  tried to import them yet.
- Wrote Alembic from scratch -- `alembic.ini`, `migrations/env.py`,
  `migrations/versions/0001_initial_schema.py` -- since no migration had
  ever been recovered, only the models. Hand-wrote the initial migration
  (all 11 tables) instead of autogenerating, baking in both known
  pgvector bugs from LOCAL_SETUP.md warning 1 from the start: `CREATE
  EXTENSION IF NOT EXISTS vector`, and importing `pgvector.sqlalchemy.
  Vector` for the `content_chunks.embedding` column. `env.py` swaps
  `+asyncpg` for `+psycopg2` for Alembic's own sync connection, per
  warning 2, from the single `DATABASE_URL`.
- Pinned `psycopg2-binary==2.9.9` in `requirements.txt` for that sync
  driver.
- Confirmed Python 3.12.10 venv, created and activated correctly inside
  `backend/` this time (a stray pre-existing `.venv` at the project
  root, and a first attempt using `.venv\Scripts\activate` without the
  `.ps1` extension in PowerShell, both silently led to a global-Python
  install on the first pass -- recreated clean once noticed).
- `docker compose up -d` -> `alembic upgrade head` -> `uvicorn app.main:app
  --reload` -> `GET /health` returned `{"status": "ok", "environment":
  "development"}` with all 11 tables + `alembic_version` confirmed via
  `psql \dt`.

**Not done yet (next steps, per REBUILD_SPEC.md):**
- `tutor.py` / `tutor_orchestration.py` / `personalization.py` /
  `diagnosis.py` -- the actual tutor logic the placeholder stands in for.
- MathGuard (`math_guard.py` / `math_validator.py`) and its regression
  suite.
- Seeding the 12 CAPS topics; frontend; authentication; quiz engine; RAG
  grounding.

---

## 2026-11-08 (2) -- Tutor logic rebuilt (REBUILD_SPEC.md step 2)

**Goal:** Replace the step-1 placeholder `app/routers/tutor.py` with the
real tutor conversation flow -- diagnosis.py, personalization.py,
tutor_orchestration.py, and tutor.py -- per REBUILD_SPEC.md Section 1
and the matching ADRs (ADR-002, ADR-003, ADR-007, ADR-010).

**Done:**
- `app/services/diagnosis.py` -- `diagnose_root_gap()`: walks a resolved
  prerequisite chain (deepest last), stops at the first topic with
  confirmed solid mastery, treats unconfirmed mastery (too few attempts)
  as a possible gap rather than a pass, and recommends the deepest
  topic that still has a gap -- which may be the originally requested
  topic itself if everything deeper is already mastered (verified this
  specific case against a wrong first assumption while writing the
  unit tests -- see tests/test_diagnosis.py).
- `app/services/personalization.py` -- `compute_pace_tier()` (14-day
  window, >=3 scored attempts required for a signal, else "on_pace")
  and `build_personalization_instructions()`. Uses `datetime.now(UTC)`
  made naive before comparing against `Attempt.created_at`, per the
  caveat in REBUILD_SPEC.md Section 1 (the schema's `created_at`
  columns are naive).
- `app/services/tutor.py` -- `build_tutor_system_prompt()` (worked
  2x+5=15 anchor, non-negotiable "explain why" rule, RAG-grounding
  placeholder, optional diagnosis note, personalization block) and
  `TutorClient` (AsyncAnthropic wrapper -- system prompt via the
  `system` param, not a message; `max_tokens=2048`).
- `app/services/tutor_orchestration.py` -- `prepare_tutor_turn()` wires
  the above three in order (diagnose -> personalize -> build prompt),
  and falls back to the "balanced" modality instead of crashing on an
  invalid/legacy `preferred_modality` value.
- `app/schemas/tutor.py` and a real `app/routers/tutor.py`: resolves the
  prerequisite chain via `Topic.prerequisite_id`, fetches scored
  attempts per topic, gets-or-creates a `TutorSession`, persists
  `TutorMessage` history both ways, and returns the reply plus the
  diagnosis's redirect flag and reasoning trace. Deliberately NOT
  included yet: `math_verified`/`verification_warnings` (MathGuard,
  step 5) and authentication (step 8).
- Added `pytest`/`pytest-asyncio` and a `pytest.ini` (with the
  `live_api` marker REBUILD_SPEC.md Section 6 describes, excluded by
  default). Wrote unit tests for all four new service modules plus
  `TutorClient` (the Anthropic call itself is mocked, not live).
- Annotated REBUILD_SPEC.md Section 1 and its rebuild-priority-order
  item 4 as done, pointing at the real files, so the spec doesn't keep
  reading like an open to-do for work that's now finished.

**Not done yet (next steps, per REBUILD_SPEC.md):**
- Running the new test suite against a real interpreter (pytest wasn't
  run end-to-end in this session -- see the handoff notes for this
  step) and a live `/tutor/message` smoke test, which needs seeded
  data (step 6) to have a real learner/topic/question to call with.
- MathGuard (step 5), seeding (step 6), frontend (step 7), auth (step 8).

---

## 2026-11-08 (3) -- MathGuard rebuilt (REBUILD_SPEC.md step 5)

**Goal:** Rebuild `math_guard.py` + `math_validator.py` -- the
protected core differentiator (ADR-011) -- from REBUILD_SPEC.md
Section 1's 12 numbered, individually-documented parsing/verification
gaps, each with its own regression test, per the project's own stated
discipline ("don't skip the adversarial tests").

**Done:**
- `app/services/math_validator.py` -- LaTeX normalization (markdown
  artifacts, unicode minus, braced SA/European decimal commas scoped
  tightly enough to never touch a coordinate pair's bare comma,
  `\times`, `\frac{}{}`, `\sqrt{}`, `\pi`, powers, reserved-symbol
  collisions I/E/S/N/O/Q via a sympy locals dict, the `in` keyword) plus
  the actual solving/comparison logic.
- Two real implementation choices worth recording for next time:
  (1) `sympy.sympify()` alone doesn't support implicit multiplication
  ("2x") -- needed `parse_expr()` with the
  `implicit_multiplication_application` transformation instead.
  (2) `sympy.solveset()` returns a correct but infinite periodic
  `ImageSet` for trig equations (e.g. every solution of sin(theta)=0.5,
  not just the two a learner would give) -- switched equation-solving
  to `sympy.solve()`, which gives the finite, learner-shaped answer
  (theta = 30, 150), and kept `solveset` only for inequalities, where
  Interval/Union containment is exactly what's needed and has none of
  that periodicity problem.
- Degree-vs-radian handling (gap 4) is deliberately scoped to direct
  trig-of-a-bare-variable only (`sin(theta)`, not `sin(2*theta)`),
  matching REBUILD_SPEC.md's own documented scope.
- Float-tolerance comparison (gap 5) was necessary for a reason beyond
  the documented `1100/1.1` case: confirmed experimentally that
  sympy's `Float(20.0) == Integer(20)` is `False` even though they're
  the same number -- exact/structural solution-set equality would have
  silently flagged correct answers as wrong.
- `app/services/math_guard.py` -- `verify_tutor_response()`: extracts
  ONLY `$$...$$` blocks (never prose), classifies each as a check step
  (zero free symbols, verified on its own, never chain-compared -- gap
  3), a solving step (one free symbol, chain-compared against the
  previous one), or left-unverified (more than one free symbol, or a
  step naming a different variable). `verified` is only ever set False
  on a positively-detected inconsistency -- never merely because
  something couldn't be parsed or judged, which is what keeps the
  "Euclidean Geometry proofs aren't equation-shaped" limitation honest
  rather than a false pass or fail.
- Wired `math_verified`/`verification_warnings` into
  `app/schemas/tutor.py` and `POST /tutor/message`, which deliberately
  left them out in step 2 pending this step.
- 19 new tests: one regression test per numbered gap
  (`tests/test_math_validator.py`) plus 7 integration tests against
  full tutor-response text (`tests/test_math_guard.py`).

**Not done yet (next steps, per REBUILD_SPEC.md):**
- Running this new test suite against a real interpreter (not done in
  this session -- see the handoff notes for this step), and a live
  end-to-end `/tutor/message` call that actually exercises MathGuard
  against a real Claude response, which still needs seeded data
  (step 6) to have a real learner/topic/question to call with.
- Seeding (step 6), frontend (step 7), auth (step 8).

---

## 2026-11-08 -- Step 6: seed_dev_data.py (rebuilt, consolidated)

**Goal:** per REBUILD_SPEC.md Section 4 + rebuild priority order item 6,
re-seed all 12 CAPS Grade 10 Pure Mathematics topics with a real
prerequisite chain, diagnostic questions, and placeholder content chunks
so `POST /tutor/message` has real data to run against for the first
time -- it could not be live-tested before this.

**Done:**
- `backend/scripts/seed_dev_data.py` -- a single idempotent script,
  deliberately consolidating the original four-script split
  (`seed_dev_data.py` + `seed_additional_topics.py` +
  `seed_more_topics.py` + `seed_stats_prob_measurement.py` +
  `seed_geometry.py`) into one, per Section 4's own recommendation.
- 12 topics: Algebraic Expressions (root), Exponents, Equations and
  Inequalities, Number Patterns, Trigonometry, Functions, Finance/Growth
  and Decay, Analytical Geometry, Euclidean Geometry, Measurement,
  Statistics, Probability -- each with a single-parent `prerequisite_id`
  chain back to Algebraic Expressions. The exact chain shape (which
  topic depends on which) is my own reasonable construction from the
  CAPS Grade 10 syllabus order, not recovered -- documented as such.
- 24 diagnostic `Question` rows (2 per topic, `is_diagnostic=True`).
- One placeholder `ContentChunk` per topic, with
  `PLACEHOLDER_EMBEDDING = [0.0] * 1536` and a `source` string that
  says plainly this is not real ingested content -- RAG ingestion
  (`scripts/ingest_content.py`) was never built, per Section 8.
- One dev `Learner` ("Test Learner", `preferred_modality="balanced"`).
- Idempotency: every entity is looked up by its natural key
  (subject name+grade, topic name within subject, question text within
  topic, content-chunk source within topic, learner display name)
  before being created, so re-running the script is safe and only
  fills in anything missing -- rather than the original's behavior
  per ADR-010, which raised `UniqueViolationError` on a second run.
- `_validate_topic_data()` fails fast (before touching the database) on
  a prerequisite name that doesn't exist or is ordered after its
  dependent, or a `DIAGNOSTIC_QUESTIONS` key that isn't a real topic
  name -- catches a typo instead of half-seeding.
- Confirmed via `async_session_factory`/`get_db` in `app/core/database.py`
  (read in full this time, not truncated) that the session-factory name
  and usage pattern match what the script imports.
- Each `Topic` is flushed individually right after creation (not batched
  at the end) specifically so its `uuid_pk()`-generated `.id` -- a
  client-side default evaluated at flush time, not at object
  construction -- is available to assign as the *next* topic's
  `prerequisite_id`.

**Not done yet (next steps, per REBUILD_SPEC.md):**
- Running the script against the real database and confirming the
  insert counts and topic/learner ids it prints (handed off to Siya to
  run and paste back).
- The live end-to-end `POST /tutor/message` smoke test this seed data
  unblocks -- still pending that run.
- Frontend (step 7), auth (step 8), everything in Section 8 (step 9).

<!-- Entries after 2026-08-03 that are known only from later project
summaries (not transcribed verbatim, since the original files were never
read in full) are captured separately in REBUILD_SPEC.md rather than
invented here. Add new BUILD_LOG entries above this line as work resumes
on the rebuilt project. -->
