# THUTOra / Ai_TUTOR — Rebuild Spec

This document is **not recovered code**. It is a detailed functional spec,
compiled from architecture decisions, build-log entries, and later project
memory, for everything that either (a) was never read verbatim during the
session that produced this recovery package, or (b) was built after that
session (26 Aug 2026) and is known to this spec only as a summary.

Everything in `README.md`, `docs/ADR-*.md`, `docs/BUILD_LOG.md`,
`docs/CAPABILITY-EVIDENCE-LOG.md`, `docs/LOCAL_SETUP.md`, and the Python/
JS/CSS files elsewhere in this recovery package **are** verbatim or
near-verbatim recovered content (each file says so at the top). This file
is the gap-filler for everything else — use it as a build checklist, not
as a source to copy-paste from.

---

## 1. Backend services described but not recovered verbatim

These were listed in the original repo (`backend/app/services/`) and their
behavior is documented across the ADRs and build log, but their literal
source was never read into any session transcript. Rebuild from the spec
below plus the matching ADR.

### `tutor.py`
**REBUILT 8 Nov 2026 -- see `backend/app/services/tutor.py`. This section is now historical context, not a to-do.**

- `build_tutor_system_prompt()` — constructs the system prompt. Must
  contain, verbatim or near-verbatim: the `2x + 5 = 15` worked example
  anchor (ADR-003), an explicit non-negotiable "explain why" instruction,
  a RAG-grounding placeholder block, and a personalization block (from
  `personalization.py`).
- `TutorClient` — thin wrapper around the `anthropic` SDK (migrated from
  an OpenAI-compatible DeepSeek client per ADR-010). Key details from
  ADR-010: system prompt passed via the dedicated `system` parameter (not
  a `{"role": "system"}` message — Anthropic's API doesn't accept that);
  response text read from `response.content[0].text`; `max_tokens=2048`
  (raised from 1024 to reduce truncation on long explanations); model
  string `claude-sonnet-4-6` (per later project memory — confirm current
  model availability on rebuild).
- Settings fields: `anthropic_api_key`, `anthropic_model` (renamed from
  `deepseek_*` per ADR-010).

### `tutor_orchestration.py`
**REBUILT 8 Nov 2026 -- see `backend/app/services/tutor_orchestration.py`. This section is now historical context, not a to-do.**

- `prepare_tutor_turn()` — pure, DB-free function. Order of operations:
  (1) run `diagnose_root_gap()` first, (2) build personalization
  instructions, (3) build the full tutor system prompt grounded on
  whichever topic the diagnosis says to actually teach (which may differ
  from what the learner asked). When diagnosis redirects, the prompt gets
  an explicit "diagnosis note" instructing the tutor to explain the
  redirect in one encouraging sentence before teaching. Falls back to
  `balanced` modality if the learner record has an invalid/legacy
  `preferred_modality` value, rather than crashing.

### `personalization.py`
**REBUILT 8 Nov 2026 -- see `backend/app/services/personalization.py`. This section is now historical context, not a to-do.**

- `compute_pace_tier()` — looks at a learner's last 14 days of attempts on
  a topic; returns `needs_support` / `on_pace` / `ready_for_extension`
  based on accuracy. Defaults to `on_pace` if fewer than 3 recent attempts
  exist. Attempts older than 14 days are excluded.
- `build_personalization_instructions()` — turns modality + pace tier into
  a system-prompt block, kept separate from the core CAPS-grounding prompt
  so it's independently testable.
- Uses `datetime.now(UTC)`, not `datetime.utcnow()` (a deprecation fix
  applied during the original build — but see the Windows timezone-aware
  vs naive `Attempt.created_at` caveat in the build log: the schema's
  `created_at` columns use naive `datetime.utcnow` defaults, so don't make
  this function's internal datetimes timezone-aware without migrating the
  whole schema in the same pass, or comparisons will break).

### `diagnosis.py`
**REBUILT 8 Nov 2026 -- see `backend/app/services/diagnosis.py`. This section is now historical context, not a to-do.**

- `diagnose_root_gap()` — takes an already-resolved, ordered prerequisite
  chain (does not query the DB itself — keeps it pure/testable) and walks
  backward through it, checking mastery at each step. Returns the deepest
  topic with insufficient OR unconfirmed mastery as the recommended
  teaching start point, plus a full human-readable reasoning trace (which
  topics were checked, why each was judged sufficient or not). Unconfirmed
  mastery (too few or no attempts) is treated as a possible gap, not a
  pass. Stops at the first topic with confirmed solid mastery.

### `risk.py` (original ADR-004 module) vs `services/risk_assessment.py` (recovered verbatim, used by `dashboard.py`)
Both exist in the codebase implementing the same three-signal logic
(declining accuracy trend, weak prerequisite mastery, disengagement).
**Consolidate into one shared module on rebuild** rather than re-forking
two copies — see the recovery note at the top of the recovered
`risk_assessment.py` in this package.

### `labs.py`
- Deterministic calculation engine, registry pattern
  (`PRACTICAL_CALCULATIONS` dict mapping `calculation_key` → function).
- `calculate_magnesium_hcl_reaction()` — the one fully-implemented and
  verified practical. Takes mass of Mg, concentration and volume of HCl,
  and an explicit `GasCondition` enum (`STP` or `RTP` — **not** a silent
  default; STP's molar gas volume is 22.4 dm³/mol, RTP's is 24 dm³/mol,
  confirmed against real NSC Data Sheets). Correctly identifies the
  limiting reagent and computes H₂ gas volume via real stoichiometry
  (Mg + 2HCl → MgCl₂ + H₂). Verified expected output: ~0.922 dm³ (STP) /
  ~0.988 dm³ (RTP) for the test-case inputs used in the build log.
- Constants: `MOLAR_MASS_MAGNESIUM_G_PER_MOL` = 24.3, molar gas volumes as
  above — these were cross-checked against the real Siyavula Grade 10
  textbook and four official NSC Physical Sciences Data Sheets.

### `math_guard.py` + `math_validator.py` — MathGuard
**REBUILT 8 Nov 2026 -- see `backend/app/services/math_guard.py` and `backend/app/services/math_validator.py`, with one regression test per numbered gap below in `backend/tests/test_math_validator.py` plus integration tests in `backend/tests/test_math_guard.py`. This section is now historical context, not a to-do.**

This is a protected core differentiator (ADR-011) — rebuild carefully and
re-run the adversarial test suite at every stage, don't assume.

Core mechanism: extract equations/inequalities directly from the LaTeX
(`$$...$$`) blocks the tutor actually renders (not from plain prose —
header text bleeding into a capture was a real, fixed bug), then use
`sympy` to compare each step's solution set against the previous step's.
Auto-detects whichever symbol is being solved for (don't hardcode `x` —
this was refactored specifically so Trigonometry/`theta`, Finance/`A,P,r,n`
etc. all work without further changes). Equations with multiple free
symbols (identities, simplification chains) are left explicitly
unverified, not guessed at.

Known, individually-fixed parsing/verification gaps to re-implement
(each should get its own regression test, per the project's own
discipline — see `docs/CAPABILITY-EVIDENCE-LOG.md`):
1. `\frac{}{}` LaTeX fraction parsing
2. Markdown artifacts (stray `**`) bleeding into equation captures
3. A "check your answer" / substitution step wrongly chain-compared
   against the solving sequence as if it were a continuation of it
4. Degree-vs-radian convention — `sympy`'s trig functions default to
   radians; CAPS teaches degrees. A correct `theta = 30` step was wrongly
   flagged against `sin(theta) = 0.5` until degree-convention handling
   was added for direct trig-of-variable expressions.
5. Floating-point rounding tolerance (e.g. `1100/1.1` not landing on
   exactly `1000.0`) — replaced strict solution-set equality with
   tolerance-based numeric comparison plus subset semantics (a later step
   may validly narrow to fewer solutions without being flagged).
6. SA/European decimal-comma notation — LaTeX's `0{,}05` idiom needs
   normalizing to a period before parsing.
7. `\times` (LaTeX multiplication) was being *deleted* rather than
   converted to `*`, leaving two numbers separated only by whitespace,
   which `sympy` can't safely read as multiplication.
8. Symbol collisions with `sympy` built-ins — `I` (imaginary unit) is
   conventionally used for Interest in Finance problems; also protect
   against `E`, `S`, `N`, `O`, `Q` colliding with `sympy` built-ins, and
   per later project memory, the `in` keyword also collided and needed
   handling.
9. Inequality direction-flipping — the classic "forgot to flip the
   inequality when dividing by a negative" error must be caught, not
   silently passed.
10. `\sqrt{}` / `\pi` handling and decimal-rounding tolerance for
    Statistics/Measurement topics.
11. Coordinate-pair notation (Analytical Geometry) must not collide with
    the decimal-comma fix above — this was a real caught bug (coordinate
    pairs like `(2,3)` look like a decimal-comma number if not handled
    carefully) that would have silently corrupted midpoint/distance
    answers.
12. Per later project memory, a Unicode minus-sign case was also found
    and fixed — LaTeX/learner input sometimes uses `−` (U+2212) rather
    than ASCII `-`.

Exposed on `POST /tutor/message` as `math_verified: bool` and
`verification_warnings: list[str]`; shown as a visible badge in the chat
UI. **Honest, permanent limitation:** Euclidean Geometry proof statements
(e.g. "the diagonals of a parallelogram bisect each other") are not
equation-shaped and cannot be verified this way — only geometry problems
that reduce to a solvable equation (angle-sum problems, etc.) get real
verification. Don't try to "fix" this by guessing at proof validity.

---

## 2. Database — fields/tables known to exist but not in the recovered schema

The recovered `backend/app/models/__init__.py` in this package is a
verbatim 26-Aug-2026 snapshot. Per later project memory, at least these
additions happened after that date and are **not** in the recovered file:

- **Authentication** on `Learner` (or a new `User`/auth table) — a hashed
  password field (bcrypt via `passlib`, pin `bcrypt==4.0.1` specifically
  due to a documented `passlib`/`bcrypt` 5.x incompatibility) and whatever
  identity field the JWT (`python-jose`) login flow needs (an
  email/username column, most likely unique). A `get_current_learner`
  FastAPI dependency was added to close a prior "no auth on endpoints"
  gap — apply it to the dashboard router in particular, which had none.
- **`Topic.term`** (1–4) and **`Topic.week_allocation`** fields, aligned
  to the CAPS four-term structure — confirmed as a planned/likely-done
  schema extension.
- Expect a new Alembic migration (or migrations) covering both of the
  above; re-run the same "drop and recreate fresh, confirm `CREATE
  EXTENSION vector` is baked into the migration" verification discipline
  documented in `docs/BUILD_LOG.md`'s 2 Aug 2026 entry.

---

## 3. Frontend — components not recovered verbatim

`ChatScreen.jsx` (the actual chat UI, confirmed ~11KB in the original
repo) was never read into any session transcript — only its existence and
role (`App.jsx` renders it as the whole app) are known. Per later project
memory, by the time of the crash it supported **four teaching modalities**:

- **Text** — presumably the original markdown/KaTeX rendering of the
  tutor's response.
- **Audio** — via the Web Speech API, using the recovered
  `frontend/src/utils/tts.js` in this package (that file strips LaTeX/
  markdown before speaking).
- **Animated** — via **Framer Motion** (a dependency not present in the
  recovered `package.json`, which predates its addition — add
  `framer-motion` on rebuild), described as a "step-reveal/wipe"
  presentation of the solving steps.
- **Visual** — an SVG number-line renderer, implying at least one new
  component rendering number-line SVGs for applicable problem types.

Also not recovered: `styles/chat.css`, `styles/product-tokens.css`
(imported by `App.jsx`), and whatever UI/toggle exists for switching
modality and for the topic picker (per the recovered `api.js`, only a
subset of CAPS topics were exposed in the UI even though more were
seeded in the backend — re-check this against the full 12-topic list on
rebuild).

**Dev-environment IDs will not transfer.** The recovered `api.js`
hardcodes a `DEV_LEARNER_ID` and a `TOPIC_IDS` map of specific UUIDs —
these were generated by the original `seed_dev_data.py` run against the
original (now-gone) database. On a fresh database, re-run the seed
scripts and update these IDs (or better, fetch them dynamically instead
of hardcoding).

---

## 4. Seed & utility scripts — known to exist, not recovered

`backend/scripts/` contained (names only, logic not recovered):
`seed_dev_data.py` (original seed — Algebra topic + one dev learner),
`seed_additional_topics.py`, `seed_more_topics.py`,
`seed_stats_prob_measurement.py`, `seed_geometry.py` (the four scripts
that extended seeding to the full 12-topic CAPS Grade 10 Pure Mathematics
coverage), `audit_diagnosis.py`, `audit_topic.py` (verification/audit
tooling, purpose inferred from name), `sanity_check_claude.py` (a live
API sanity check, per its name).

Rebuild priority: a single idempotent seed script covering all 12 topics
with real prerequisite chains back to Algebra, diagnostic questions per
topic, and content chunks (even if `content_chunks` ingestion is still a
placeholder for RAG purposes) is more valuable than recreating the
original four-script split.

~~`sanity_check_claude.py`~~ -- **DONE 8 Nov 2026**, rebuilt as a genuine
standalone live-API check (isolates the Anthropic call from the DB/
FastAPI stack, never prints the key itself) -- written while diagnosing
an `invalid x-api-key` 401 during the step 6 smoke test, not purely from
the original name as first guessed. `audit_diagnosis.py`/`audit_topic.py`
remain not recovered -- purpose still inferred from name only.

---

## 5. PowerShell scripts — known to exist, described only

`scripts/windows-setup.ps1` — installs Git, Python 3.12, VS Code, Docker
Desktop via `winget`; checks/enables WSL2; installs VS Code extensions if
`code` is on PATH. `scripts/start-dev.ps1` — starts Docker, polls
`pg_isready` (up to 60s) rather than trusting "container is Up", creates
venv + installs deps on first run only, prompts to fill `.env` via
Notepad if missing, runs `alembic upgrade head` (safe every time), starts
`uvicorn`; supports `-SkipDocker`/`-SkipInstall` flags. `scripts/
stop-all.ps1` and `scripts/start-all.ps1` also existed (content unknown).

**Known Windows gotcha to build in from the start this time:** PowerShell's
`Out-File` corrupts files with a BOM — use
`[System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($false))`
instead, in any script that writes files.

---

## 6. Testing

Per later project memory, the test suite reached **50 tests** (up from the
13 files/subset confirmed in the 26-Aug session). Known additions beyond
the recovered MathGuard/per-topic suites: a `conftest.py` enforcing
`WindowsSelectorEventLoopPolicy` on Windows, and a `sys.modules` check in
`database.py` that scopes `NullPool` to pytest specifically (an
asyncpg-on-Windows fix). `pytest.ini` uses `addopts` to exclude
`@pytest.mark.live_api`-marked tests from default runs.

---

## 7. Governance / compliance documents — not recovered

A Word document was produced covering POPIA compliance considerations for
learner data processing: access-control gaps, Claude API as an external
processor (cross-border data transfer implications), and a risk register
numbered R1–R10. **Content not recovered** — this needs to be rewritten
from scratch, ideally by someone with current POPIA knowledge rather than
guessed at. Architecture diagrams were also produced (format/tool:
mentioned use of matplotlib for diagram generation per later memory) —
also not recovered.

---

## 8. Known open items as of the last captured status (not yet built)

- **Quiz engine** — 3-tier randomly-generated equations, 100%-to-pass
  mechanic. Not built as of the last captured status.
- **RAG grounding** — `content_chunks` ingestion pipeline
  (`scripts/ingest_content.py`) was never built; tutor grounding was still
  a placeholder string throughout the project's life, as far as is known.
- **Teacher dashboard UI** — the API exists (recovered verbatim in this
  package) but had no frontend, and was lower priority than learner-facing
  features.
- **Video resource generation** — on the roadmap, deferred.
- **Deployment hardening** — Oracle Cloud Free Tier via Coolify was the
  target but hardening was still pending.

---

## 9. Brand & long-term vision context

- The product is branded **THUTOra** ("Learn Smarter. Achieve More. Shape
  Your Future.") under parent company Zynora Technologies ("Innovate.
  Integrate. Elevate.") — two deliberately separate brand identities.
- By the last captured status, the frontend was being scaffolded with
  THUTOra brand tokens: navy `#0D1B2A`, teal `#00BFA6`, purple `#6C5CE7`
  — **different** from the originally-sampled Zynora black/cyan tokens in
  `docs/ADR-008-brand-design-tokens.md` and the reconstructed
  `frontend/src/styles/tokens.css` in this package. Decide explicitly
  which palette is authoritative before re-skinning on rebuild.
- Grade 10 CAPS Mathematics is considered complete; planned expansion is
  Maths first to other grades (11/12), then other subjects (Physical
  Sciences, Life Sciences, Accounting) — consistent with the "depth over
  breadth" philosophy (ADR-006) applied repeatedly, not abandoned.
- **Longer-term vision**: evolve THUTOra from a single-tenant Maths tutor
  into an **Education Platform as a Service (EdPaaS)**, with a conceptual
  access/role model spanning: student, teacher/parent, principal, district
  manager, circuit manager, provincial MEC, and national tiers. The stated
  intent is to build this identity/access schema **additively/greenfield**
  (not reverse-engineered from the current 11-table schema), and to
  sequence dashboards in two tracks: product-embedded per-role dashboards
  first, then a separate BI tool on an analytics warehouse for
  circuit-and-up reporting later. This is a planning-stage direction, not
  yet implemented — treat it as context for architectural decisions on
  rebuild (e.g. don't paint yourself into a single-tenant corner), not as
  a rebuild requirement in itself.

---

## 10. Rebuild priority order (suggested)

1. Git + private GitHub remote, on the new machine, before anything else.
2. Toolchain install (Python 3.12, Docker Desktop, Git, VS Code, Anthropic
   key) using `docs/LOCAL_SETUP.md` in this package.
3. Restore the recovered backend core (models, main.py, dashboard
   service/router, risk_assessment.py) and get `/health` passing against
   a fresh local Postgres + migration, exactly as `LOCAL_SETUP.md`
   describes.
4. ~~Rebuild `tutor.py`, `tutor_orchestration.py`, `personalization.py`,
   `diagnosis.py` from Section 1 above~~ -- **DONE 8 Nov 2026**, with unit
   tests in `backend/tests/`. `POST /tutor/message` is wired end-to-end
   against the real schema; `math_verified`/`verification_warnings` are
   still pending step 5 (MathGuard).
5. ~~Rebuild MathGuard (`math_guard.py` / `math_validator.py`) with its full
   regression-test suite from Section 1~~ -- **DONE 8 Nov 2026**. All 12
   numbered gaps have a dedicated regression test; `POST /tutor/message`
   now populates `math_verified`/`verification_warnings` for real.
6. ~~Re-seed all 12 CAPS topics with prerequisite chains and diagnostic
   questions (Section 4)~~ -- **DONE 8 Nov 2026**. One idempotent script
   (`backend/scripts/seed_dev_data.py`), consolidating the original
   four-script split per this section's own recommendation. 12 real CAPS
   Grade 10 Pure Mathematics topics, single-parent prerequisite chain
   rooted at "Algebraic Expressions," 24 diagnostic questions (2/topic),
   one placeholder `ContentChunk` per topic (explicitly non-real --
   RAG ingestion per Section 8 was never built), one dev `Learner`.
7. Rebuild the frontend chat UI, starting with Text + Audio modalities
   (both fully specified / partially recovered) before attempting the
   Animated/Visual modalities, which are the least-specified pieces here.
8. Re-add authentication (Section 2) before any dashboard or multi-learner
   feature goes anywhere near real data.
9. Everything in Section 8 (quiz engine, RAG grounding, deployment
   hardening) as genuinely new work, not recovery.
