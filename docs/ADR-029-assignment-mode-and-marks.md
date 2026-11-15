# ADR-029: Assignment mode (practice/test) and per-question marks

**Status:** Accepted
**Date:** 15 November 2026

## Context

ADR-028's Assignments feature was live-tested end to end for the first time
this session (see `docs/BUILD_LOG.md`'s "ADR-028 live-tested end to end"
entry). The moment a real student answered a real wrong answer, two design
gaps that unit tests and code review hadn't surfaced became obvious: the
AI-marking feedback reveals the correct answer and a full explanation the
instant a wrong answer is submitted, which is exactly right for practice but
defeats the purpose of anything meant as a real assessment -- a student can
simply retry until they're told the answer; and every question counted for
exactly one point, with no way for a teacher to weight a harder question
more than an easier one.

In the same message, Siya asked whether this "can be like Moodle app but
more simplistic." Scoped via `AskUserQuestion`, both answers marked
"Recommended":

- **Feedback timing:** a toggle when creating an assignment -- "Practice"
  shows AI feedback immediately, exactly as every assignment behaved before
  this; "Test" withholds the correct answer/explanation until the teacher
  explicitly releases results.
- **Scoring:** per-question marks, default 1, editable per question when a
  teacher adds it to an assignment. A student's total score is the sum of
  marks for correctly-answered questions.

A third change rides along, not separately asked about but needed to make
"derive some questions from the textbook" (Siya's own phrase) actually
possible: a teacher can now browse and reuse the seeded CAPS question bank
and their own previously-authored custom questions when building an
assignment, not only author new ones from scratch (ADR-028's own Open Items
flagged this exact gap explicitly).

**Deliberately NOT a Moodle clone.** Siya's question was answered with a
direct recommendation, not a literal "yes, build Moodle": no new question
types (short-answer/text stays the only kind, matching ADR-028's scope), no
time limits, no randomized question pools, no complex weighting beyond a
plain per-question integer. Moodle's own scope is a different product; this
stays THUTOra's deliberately simpler assignments feature with two real gaps
closed, not a rebuild.

## Decision

**The real mark is always computed and stored; only what's shown to the
student is gated.** `submit_assignment_answer()` (`app/services/assignments.py`)
is unchanged in this respect -- it always calls `mark_answer()` and always
writes a real `Attempt` row with the genuine `is_correct`/`ai_feedback`,
test-mode or not. Visibility gating happens entirely in the router layer
(`app/routers/learner_assignments.py`'s `_withholds_feedback()`), which nulls
`is_correct`/`ai_feedback` in the HTTP response -- never in the database --
whenever `Assignment.mode == "test"` and `Assignment.results_released` is
still `false`. This is the same posture ADR-028 already established for
`model_answer` (never returned to the student) and keeps a single source of
truth: nothing is ever computed twice or stored in two places that could
drift.

**`Assignment` gains two columns:** `mode` (`"practice"` default, `"test"`)
and `results_released` (boolean, default `false`). `results_released` is a
one-way switch for this pass -- `release_assignment_results()` sets it and
there is no "unrelease"; a teacher who releases results early has no way to
re-hide them, which is an accepted limitation rather than an oversight (the
same "ship the simple version, add the edge case if it's actually needed"
posture ADR-028 took with due-date enforcement).

**`AssignmentQuestion` gains `marks`** (integer, default 1) -- the point
value a question is worth **in this specific assignment**, not a property of
the `Question` row itself. The same question can be reused across multiple
assignments (ADR-028's Scope section already established this for
custom-authored questions) worth a different number of marks each time,
which is why marks lives on the join table and not on `Question`.

**`get_assignment_completion()`'s scoring is fixed to dedupe by latest
attempt per question**, not summed across every attempt row. This was a
latent bug in ADR-028's original implementation: a student can resubmit via
AssignmentsView.jsx's existing "Re-submit answer" button, writing a second
`Attempt` row rather than updating the first (consistent with `Attempt`
being append-only everywhere else in this app). The original `sum(1 for a in
attempts if a.is_correct is True)` could double- or under-count a
resubmitted question depending on row order. Attempts are now queried
ordered by `created_at` and reduced to one (the latest) per `question_id`
before counting -- for both the existing `correct_count` and the new
`marks_earned`.

**The question-bank endpoint (`GET /teach/questions?topic_id=...`) is scoped
to "seeded or mine," never "every teacher's."** `list_bank_questions_for_topic()`
returns a `Question` for the topic where `created_by_user_id IS NULL` (the
seeded/CAPS bank) or `created_by_user_id == teacher.id` (this teacher's own
custom questions) -- never another teacher's custom question, which stays
private to the assignments they build it into. This is a judgment call, not
something Siya specified: a school-wide shared custom-question bank is a
reasonable future ask, but defaulting to private avoids one teacher's
possibly-wrong or half-finished custom question silently appearing in a
colleague's assignment-building flow before that's actually asked for.

**Marks are always shown to the student, even when results are withheld.**
A "test"-mode question whose feedback is withheld still reports its own
`marks` value in both `GET /assignments/{id}` and the answer-submission
response -- the same information a printed exam gives by stating "[5 marks]"
next to a question before it's marked. Only `is_correct`/`ai_feedback` (and,
by extension, `marks_earned`/the running score, which would otherwise leak
correctness) are withheld.

## Scope, explicitly bounded for this pass

- **No "unrelease."** Once a teacher releases a test's results, there's no
  way to re-hide them from this UI. A real gap if a teacher releases by
  mistake, left for whenever it's actually needed.
- **No per-question mode.** Mode is one choice for the whole assignment, not
  configurable per question within it.
- **Marks are a plain integer per question (1-100), nothing more.** No
  partial-credit grading, no rubrics, no weighted categories.
- **The question bank is private per teacher**, not shared school-wide (see
  Decision above) -- a deliberate judgment call, flagged as a real future
  option rather than assumed settled.
- **Still no `Class`/group targeting or due-date enforcement** -- unchanged
  from ADR-028's own bounded scope, not reopened here.

## Consequences

- `backend/migrations/versions/0007_add_assignment_mode_and_marks.py`: three
  new columns, all additive with server-side defaults matching every
  pre-existing row's actual behaviour.
- `backend/app/models/__init__.py`: `Assignment.mode`/`results_released`;
  `AssignmentQuestion.marks`.
- `backend/app/schemas/assignments.py`: `AssignmentCreateRequest.questions`
  (replacing the flat `question_ids` list) + `mode`; `mode`/
  `results_released`/`marks_earned`/`marks_total`/`feedback_withheld` added
  across the response schemas as appropriate; `CustomQuestionResult` gained
  `created_by_user_id` so the new bank-browse list can tell a teacher's own
  question apart from a seeded one.
- `backend/app/services/assignments.py`: `create_assignment()` takes
  `(question_id, marks)` pairs and a `mode`; new
  `release_assignment_results()` and `list_bank_questions_for_topic()`;
  `submit_assignment_answer()` now also returns the question's `marks`;
  `get_assignment_completion()`'s dedup fix (see Decision above).
- `backend/app/routers/teach_assignments.py`: new `GET /teach/questions` and
  `POST /teach/assignments/{id}/release`; existing endpoints updated for the
  new request/response shapes.
- `backend/app/routers/learner_assignments.py`: `_withholds_feedback()`
  gates `is_correct`/`ai_feedback`/`marks_earned` across all three endpoints;
  the real mark is always written to `Attempt` regardless.
- `frontend/src/components/TeacherAdminScreen.jsx`: a mode selector and
  per-draft-question marks input in `CreateAssignmentForm`; a "reuse an
  existing question" bank list fed by the new endpoint; a "Release results"
  button and marks columns in `AssignmentsPanel`.
- `frontend/src/components/AssignmentsView.jsx`: shows each question's marks;
  renders a neutral "Submitted -- your teacher will release the result"
  state instead of a correct/incorrect verdict when withheld.
- `frontend/src/api.js`: `createAssignment()` now sends `questions`
  (question_id + marks) and `mode`; new `releaseAssignmentResults()` and
  `fetchBankQuestions()`.
- Verified: real imports of every changed/new backend module; full
  `pytest tests/` (same three `datetime.UTC`-blocked files excluded) -- 148
  passed, zero regressions; real `npx vite build` (clean) and `npx eslint
  src/` (7 pre-existing `react-hooks/set-state-in-effect` occurrences
  unchanged, no new category of issue).

## Open items (explicitly not done, not silently dropped)

- **Not live-tested.** Nobody has yet created a real Test-mode assignment,
  had a real student answer it, confirmed the feedback is genuinely withheld
  in a real browser session, and clicked a real "Release results" button to
  confirm it then appears. This is the natural next live-test priority,
  ahead of the rest of `docs/LIVE_TEST_CHECKLIST.md`'s deferred priorities.
- **Migration 0007 has not been run against the real Postgres instance** --
  verified by `ast.parse` only, same depth every prior migration in this
  project got before its own first live test.
- **No "unrelease," no per-question mode, no shared question bank across
  teachers** -- see Scope above; real, named, deferred decisions, not
  oversights.
