# ADR-020: Add English Home Language and isiZulu Home Language (Grade 10)

**Status:** Accepted
**Date:** 14 November 2026

## Context

Siya's request: add English and isiZulu as Home Language subjects, on the
observation that students across South Africa don't all study the same
subjects, but every official language's Home Language curriculum follows
the same national CAPS framework for a given grade. Checked this against
the DBE's own Grade 10 Home Language Annual Teaching Plans (the national
document covers all 12 official languages' Home Language ATPs together,
14 Nov 2026): the observation is correct. Every language's Grade 10 Home
Language plan runs on the same four CAPS skill strands -- Listening and
Speaking, Reading and Viewing, Writing and Presenting, and Language
Structures and Conventions (the CAPS document itself describes the last
one as "integrated into all skills" rather than taught as a standalone
block) -- and the final exam scores against this same shape: Language in
Context, Literature, Writing, and Orals. What differs per language is the
content hanging off that shared skeleton (which novel, poems, and idiom
get taught), not the skeleton itself.

This is the first subject whose content isn't equation- or ledger-shaped
at all -- Accounting (ADR-018) at least had a handful of numeric-equality
checks (VAT, trial balance); Home Language content (essay writing,
literature analysis, oral performance) has no single-correct-answer shape
anywhere in it. It's also the first subject where correctness depends on
fluency in a specific language, not just on CAPS content knowledge --
isiZulu content needs to be linguistically correct for native-speaker
students who will notice an error immediately, in a way an English
learner working through an Accounting question would not notice a
slightly-off model_answer phrasing.

## Decision

**Architecture: one Subject per language, same shared topic template,
reusing the Subject/Topic/Question schema with zero changes** -- the same
pattern every prior subject/grade addition has confirmed. Five topics,
following the shared national skill-strand structure (collapsed from the
ATP's own finer week-by-week blocks into topic-sized units, same
granularity Grade 11 Physical Sciences started at):

1. Language Structures and Conventions -- made the root topic (not a leaf
   named last, despite CAPS describing it as "integrated"): grammar and
   language mechanics genuinely underlie the other four skills, so this
   is where root-cause diagnosis should land first.
2. Listening and Speaking
3. Reading and Viewing: Literature (Poetry and Drama)
4. Reading and Viewing: Visual and Media Texts
5. Writing and Presenting

...chained in that order as one linear trunk (no branches needed at this
topic count, same shape Grade 10 Accounting's own backbone started with
before branching). **Both "English Home Language" and "isiZulu Home
Language" use these exact same five topic names** -- the same "same name
reused across a different Subject row" convention Grade 10/11 already
established for grades, applied here across languages instead, because
the underlying skill really is the same skill.

**Literature content deliberately stays text-agnostic.** The ATP itself
does not name which novel, drama, or poems to teach -- that list comes
from a separate DBE prescribed-text circular that gets revised every few
years and differs per language, and this ADR does not have reliably
current data on what's currently prescribed for either English or
isiZulu Grade 10. Seeding a specific title risks teaching to a text
that's no longer prescribed, which is a real inaccuracy, not a
stylistic gap. Literature topic questions therefore stay genre-general
(poetic devices, stage-direction conventions, praise-poetry form) rather
than tied to a named text. If/when Siya supplies the current prescribed
list, that becomes additional seed content under the same topic, not a
schema change.

**Verification: zero, and more definitively than any prior subject.**
ADR-018's "no MathGuard checking yet, honest limitation" posture for
Accounting extends here, but Home Language content doesn't even have
Accounting's handful of numeric-equality edge cases -- there is no
equation-shaped subset anywhere in this subject. `model_answer` for
essay/writing-type questions is rubric-style guidance (what a strong
answer covers), not a model answer to match against -- an extension of
the same "model_answer as guidance, not hard match" pattern Accounting's
conceptual questions already used informally. `math_guard.py`/
`math_validator.py` are unchanged.

**isiZulu content ships now, explicitly flagged as unreviewed.** Given
the accuracy risk described in Context, three options were on the table:
ship isiZulu content now flagged for review; build the topic skeleton
only and leave content to a fluent reviewer; or hold off on isiZulu
entirely until English is live. Siya's choice: build it now, using the
same "ship then verify" discipline this project already applies to
every other kind of correctness (MathGuard gaps, auth bugs, attachment
bugs) -- but applied to language accuracy instead of logic, and with an
explicit, loud flag that this content has NOT been reviewed by a fluent
isiZulu speaker and should not be treated as authoritative until Siya
(or someone he trusts) checks it. This is a materially different kind
of "not done yet" than every prior ADR's open-items list: those were
missing features or untested code paths; this is unverified correctness
of the content itself. isiZulu examples were deliberately kept to simple,
well-documented linguistic facts (the noun-class system, basic
vocabulary) rather than attempting idiomatic or complex sentence
construction, to bound the risk, but "simple" is not the same as
"verified."

**No new frontend symbol-keyboard entries.** Home Language topics need
none of `SymbolKeyboard.jsx`'s existing rows (no equations, no Rand
signs) -- confirmed by reading the component: an unmatched topic name
already falls back to `COMMON_SYMBOLS` alone (brackets, equals, square
root), which is harmless if not particularly useful for essay writing,
so no change was needed rather than suppressing it for these topics.

## Consequences

- `backend/scripts/seed_dev_data.py`: new `_ENGLISH_HL_TOPICS`/
  `_ENGLISH_HL_QUESTIONS` and `_ISIZULU_HL_TOPICS`/`_ISIZULU_HL_QUESTIONS`,
  two new `SUBJECTS` entries at grade 10. 10 new questions per language
  (20 total). No model or migration change.
- `app/services/tutor.py`, `app/routers/topics.py`,
  `frontend/src/components/SubjectTopicSidebar.jsx`: zero changes,
  confirmed by reading them, same finding as every prior addition.
- `frontend/src/components/SymbolKeyboard.jsx`: zero changes (see
  Decision above).
- `math_guard.py`/`math_validator.py`: zero changes.

## Open items (explicitly not done, not silently dropped)

- **isiZulu content is unreviewed by a fluent speaker.** This is the
  headline open item, not a footnote: do not treat the isiZulu questions
  and examples in this commit as correct until Siya (or a trusted fluent
  reviewer) has checked them. Flagged again in BUILD_LOG.md and inline
  in `seed_dev_data.py` itself so it can't be missed later.
- **No current prescribed-text list for either language.** Literature
  topic content stays genre-general until Siya supplies or confirms the
  actual current DBE prescribed novel/poetry/drama list for each
  language.
- **Not live-tested against a real Claude call yet.** Same handoff as
  every previous content addition.
- **No Home-Language-specific grading/feedback mechanism.** Essay-type
  questions have no rubric-scoring infrastructure beyond the tutor
  reading `model_answer` as guidance in its prompt -- there is no
  structured rubric field on `Question` yet. Revisit if/when this
  becomes a real pain point, same "don't build infrastructure before a
  real need shows up" discipline as every other open item in this
  project.
- **Grade 11/12 Home Languages** don't exist yet.
- **Other official languages** (isiXhosa, Afrikaans, Sesotho, etc.) are
  not in scope for this ADR -- the architecture generalizes cleanly
  (same shared topic template, new language-specific content), but
  building more languages is a future, explicitly-requested step, not
  assumed here.
