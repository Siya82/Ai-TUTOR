# ADR-025: THUTOra EdPaaS product architecture -- CORE, LEARN, TEACH, CONNECT, INSIGHTS

**Status:** Accepted
**Date:** 15 November 2026

## Context

Siya defined the concrete shape of the THUTOra EdPaaS vision that project memory has referenced only abstractly since 12 Nov 2026 ("evolve THUTOra from a single-tenant Maths tutor into an Education Platform as a Service, with a conceptual data/access model spanning student, teacher/parent, principal, district manager, circuit manager, provincial MEC, and national tiers"). That abstract tier list now has a concrete product shape:

- **THUTOra LEARN** -- AI tutor, adaptive learning, lessons, practice exercises and assessments. The student-facing product.
- **THUTOra TEACH** -- class analytics, learner diagnostics, intervention tools, lesson planning and assessment management. The teacher-facing product.
- **THUTOra CONNECT** -- a parent-facing experience connecting parents with their learner's educational progress.
- **THUTOra INSIGHTS** -- school-to-national education analytics, curriculum gaps, intervention effectiveness, and programme evaluation.

All four sit on **THUTOra CORE**: one shared technology, data, and services foundation, rather than four independently-built applications that happen to share a brand.

This arrives at a notable moment: the teacher dashboard auth gate and bulk student provisioning UI, shipped earlier the same day (ADR-024), is -- without having been planned under this name -- the first real slice of TEACH. This ADR exists to name the architecture explicitly and map what already exists to it, so every build decision from here (a new feature, a new role, a new table) can be reasoned about as "which product is this for, and does CORE already support it" rather than as an undifferentiated pile of backend/frontend code.

## Decision

**THUTOra CORE is the data/service layer every product draws from, and it mostly already exists** -- it just hasn't been named or organized as a distinct layer before now:
- The database schema (`Subject`, `Topic`, `Learner`, `User`, `School`, `Attempt`, `Question`, `ContentChunk`, `TutorSession`/`TutorMessage`, `Attachment`) is CORE. `User.role` (ADR-017) is specifically what lets CORE serve more than one product's user base from one identity table.
- MathGuard (`math_guard.py`/`math_validator.py`), the root-cause diagnosis engine (`diagnosis.py`), personalization (`personalization.py`), and the RAG retrieval pipeline (`embeddings.py`/`retrieval.py`) are CORE -- pedagogical/data logic no single product UI owns.
- The Anthropic Claude integration itself (`app/services/tutor.py`'s `TutorClient`) is CORE infrastructure, even though today only LEARN calls it.

**THUTOra LEARN is the existing student-facing surface, named retroactively:** `ChatScreen.jsx`, `POST /tutor/message`, `POST /attachments`, and everything gated behind `get_current_learner`. No code changed by this ADR -- this is the naming catching up to what already shipped across ADR-001 through ADR-023.

**THUTOra TEACH is the dashboard/admin work from ADR-024, named the same way:** `TeacherAdminScreen.jsx`, `GET/POST /admin/*`, `GET /api/v1/dashboard/*`, and everything gated behind `get_current_teacher`. TEACH's own roadmap (class analytics beyond the roster, lesson planning, assessment management) is explicitly broader than what ADR-024 shipped -- ADR-024 is TEACH's first slice, not all of it.

**THUTOra CONNECT does not exist yet, and needs a genuinely new relationship CORE doesn't model today:** a parent role (`User.role = "parent"`, following the same pattern teacher did) plus a parent-to-learner link. This is NOT the same shape as TEACH's teacher-to-school scoping (ADR-024's `_assert_same_school`) -- a parent needs to see one or more SPECIFIC learners (their own children), not every learner in an institution, and a parent account plausibly needs linking to more than one child. Whether that's a join table (`parent_learner_links`) or a FK on `Learner` mirrors the exact design question ADR-017 already resolved once for `Learner.user_id` -- likely a join table this time, since a parent-to-children relationship is naturally many-to-many in a way a student-to-one-account relationship never was. Not designed in detail here -- flagged as the shape of the next decision CONNECT will require, not decided in advance of actually building it.

**THUTOra INSIGHTS likely isn't an in-app product screen at all, consistent with a decision already on record:** project memory already states the plan to "sequence dashboards in two tracks: product-embedded per-role dashboards first, a BI tool on an analytics warehouse for circuit-and-up reporting later" (12 Nov 2026). INSIGHTS -- school-to-national analytics -- is that second track. It most likely means an analytics warehouse fed by CORE's data, queried by a BI tool, rather than a fifth React frontend with its own dashboard screens. This ADR doesn't commit to that shape, just notes that INSIGHTS is the one product of the four that may not look like LEARN/TEACH/CONNECT at the code level at all.

**No code or file renaming is done by this ADR.** `ChatScreen.jsx` isn't renamed to anything LEARN-branded, `TeacherAdminScreen.jsx` isn't renamed to anything TEACH-branded, and no directory restructuring (e.g. splitting `app/` into a `core/` package plus per-product packages) happens here. This ADR is a naming and planning decision, not a refactor -- whether/when to actually reorganize the repo to mirror this architecture is a separate decision, not made in this pass.

## Consequences

- No code changes. This ADR is documentation only -- the next ADR that touches CONNECT, INSIGHTS, or any further TEACH work should reference this one for which product it belongs to and what CORE already offers it.
- Every future role addition (parent, admin, principal, district/circuit/provincial tiers) should be evaluated against this same CORE/product split: does the new capability belong in CORE (shared data/logic) or in one product's own UI/routes, the same question ADR-024's dashboard-scoping decision implicitly answered for TEACH.
- The THUTOra brand's existing four-subject marketing vision (Mathematics, Physical Sciences, Life Sciences, Accounting -- ADR-012/ADR-013) is a CURRICULUM axis, orthogonal to this PRODUCT axis. LEARN serves whatever subjects CORE has content for; adding a subject (ADR-013 through ADR-023) is a CORE/LEARN-content question, not a new product.

## Open items (explicitly not done, not silently dropped)

- **CONNECT is unbuilt.** No parent role, no parent-learner link table, no parent-facing UI. The next step if/when Siya prioritizes it is designing that link (join table vs. FK, one parent-many-children vs. one-to-one) before writing any code, the same way ADR-017 designed the Learner/User split before building student login.
- **INSIGHTS is unbuilt and may not be a traditional product screen.** Likely a BI-tool-on-a-warehouse build, per the 12 Nov 2026 sequencing decision already on record -- not designed further here.
- **No repo-level reorganization.** `app/` is not split into `core/` + per-product packages; whether that's ever worth doing (vs. just reasoning about the split conceptually, as this ADR does) is an open question, not a planned task.
- **No renaming of existing files/components to product-branded names** (e.g. `ChatScreen.jsx` -> something LEARN-branded). Purely cosmetic, deliberately not done alongside a documentation-only ADR.
- **TEACH's own roadmap beyond ADR-024** (lesson planning, assessment management, class-level analytics beyond the roster) is real CAPS-adjacent scope not built yet -- ADR-024 is explicitly TEACH's first slice, not a claim that TEACH is complete.
