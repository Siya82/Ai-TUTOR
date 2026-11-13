"""
TutorClient and the tutor system prompt builder.
See docs/ADR-003-explain-every-transformation.md and
docs/ADR-010-deepseek-to-anthropic-migration.md.

REBUILD NOTE: rebuilt from REBUILD_SPEC.md Section 1 plus those two
ADRs -- not recovered code. The exact prompt wording below is this
rebuild's own, written to satisfy the specific requirements the spec
calls out (the 2x+5=15 anchor, the non-negotiable "explain why" rule, a
RAG-grounding placeholder, and the personalization block) -- it is not
a literal reproduction of lost text, and is a reasonable place to start
iterating once real learner transcripts exist (see ADR-003's own
Consequences section on this).

FIX 8 Nov 2026 (found via the step 6 live /tutor/message smoke test, not
a unit test): this prompt did not originally instruct Claude to wrap
equations in $$...$$ -- MathGuard (math_guard.py) only ever extracts
$$...$$ blocks (per REBUILD_SPEC.md's own description of the original
tutor's output), so without this rule math_verified would always come
back True with a "no blocks found" warning, never actually verifying
anything in production. Added _MATH_FORMATTING_RULE and updated the
calibration anchor itself to demonstrate the required $$...$$ format.

FIX 12 Nov 2026 (multi-subject support, ADR-013): build_tutor_system_prompt()
and the RAG-grounding placeholder were hardcoded to "Mathematics". Both
now take subject_name/grade so a second subject (Physical Sciences,
Physics strand) introduces itself correctly instead of every tutor turn
claiming to be a Maths tutor regardless of the real topic's subject.
"""

from anthropic import AsyncAnthropic

from app.core.config import settings

# Raised from 1024 to 2048 per ADR-010, to reduce truncation risk on
# longer, multi-step explanations.
MAX_TOKENS = 2048

_WORKED_EXAMPLE_ANCHOR = """\
Calibration example -- match THIS depth of explanation on every problem, not just this one. \
Note the $$...$$ formatting around every equation line -- this is required, see the MATH \
FORMATTING RULE below.

Problem: Solve for x:
$$2x + 5 = 15$$
Step 1: Subtract 5 from both sides:
$$2x = 10$$
  Why this is valid: subtracting the same value from both sides preserves equality -- \
whatever you do to one side of an equation, you must do to the other, or it stops being a \
true statement.
Step 2: Divide both sides by 2:
$$x = 5$$
  Why this is valid: dividing both sides by the same non-zero number also preserves \
equality, and dividing the coefficient of x by itself is exactly what isolates x.
Check: substitute x = 5 back into the original equation:
$$2(5) + 5 = 15$$\
"""

_MATH_FORMATTING_RULE = """\
MATH FORMATTING RULE (do not skip this -- it is what lets your work be checked automatically): \
every equation or inequality that is a distinct step -- the original problem restated, every \
intermediate transformation, the final solution, and any substitution check -- must appear on \
its own line wrapped in double dollar signs, exactly like $$2x + 5 = 15$$, as shown in the \
calibration example above. Do not put an equation only inside a markdown code span or plain \
prose -- it will not be checked unless it is a standalone $$...$$ line. Do not wrap \
non-equation text (vocabulary, headings, explanations) in $$...$$.\
"""

_EXPLAIN_WHY_RULE = """\
NON-NEGOTIABLE RULE: for every transformation or step you show, you must explain WHY it is \
valid -- not just state what the step is. A learner who only sees "what happened" without \
"why it's allowed" has not been taught, even if the arithmetic is correct. If a learner asks \
"why?" again about something you already explained, re-explain it differently (do not repeat \
the same wording), and consider whether they are actually asking about a more foundational \
concept underneath the one you just covered.\
"""

def _build_rag_grounding_placeholder(subject_name: str, grade: int) -> str:
    """
    FIX 12 Nov 2026 (multi-subject support): this used to be a module-level
    constant that hardcoded "Mathematics" -- fine while THUTOra was
    Maths-only (ADR-006), wrong the moment a second subject (Physical
    Sciences) was seeded, since every tutor turn for every subject would
    still claim to be grounded in "Mathematics curriculum knowledge."
    Turned into a function parameterized by the real Subject row instead.
    """
    return (
        f"[CAPS content grounding: not yet wired to real retrieval -- content_chunks "
        f"ingestion is a known placeholder, see REBUILD_SPEC.md Section 8. Answer from "
        f"general CAPS Grade {grade} {subject_name} curriculum knowledge until this is "
        f"implemented.]"
    )


def build_tutor_system_prompt(
    topic_name: str,
    personalization_block: str,
    subject_name: str = "Pure Mathematics",
    grade: int = 10,
    diagnosis_note: str | None = None,
) -> str:
    """
    Builds the full tutor system prompt. Always includes, in order: a
    short framing line naming the SUBJECT and topic (FIX 12 Nov 2026,
    multi-subject support -- see _build_rag_grounding_placeholder's own
    note; subject_name/grade default to the original Pure Mathematics
    values so any caller not yet updated keeps its old behaviour), the
    worked-example calibration anchor, the non-negotiable "explain why"
    rule, the RAG-grounding placeholder block, an optional diagnosis note
    (present only when tutor_orchestration.prepare_tutor_turn() redirected
    teaching to a prerequisite topic), and the personalization block from
    personalization.py.

    The $$...$$ math-formatting rule and worked-example anchor are kept
    for every subject, not just Mathematics -- Physical Sciences content
    (kinematics, Ohm's Law, Coulomb's Law, etc.) is equally equation-
    shaped and MathGuard verifies it the same way. This does NOT
    generalize to every possible subject (e.g. purely descriptive
    content has nothing for MathGuard to check), which is exactly why
    Physical Sciences rebuild started with the Physics strand only --
    see ADR-013.
    """
    sections = [
        f"You are THUTOra, a CAPS-aligned Grade {grade} {subject_name} tutor. The current "
        f"topic is: {topic_name}.",
        _WORKED_EXAMPLE_ANCHOR,
        _MATH_FORMATTING_RULE,
        _EXPLAIN_WHY_RULE,
        _build_rag_grounding_placeholder(subject_name, grade),
    ]
    if diagnosis_note:
        sections.append(diagnosis_note)
    sections.append(personalization_block)
    return "\n\n".join(sections)


class TutorClient:
    """Thin wrapper around the Anthropic SDK (migrated from DeepSeek per ADR-010)."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._client = AsyncAnthropic(api_key=api_key or settings.anthropic_api_key)
        self._model = model or settings.anthropic_model

    async def ask(self, system_prompt: str, messages: list[dict]) -> str:
        """
        messages: a list of {"role": "user" | "assistant", "content": ...}
        dicts, in order -- NOT including the system prompt. Anthropic's
        API takes the system prompt via the dedicated `system` parameter
        rather than a {"role": "system"} message in `messages`, which it
        does not accept (ADR-010).

        `content` is usually a plain string, but the Anthropic SDK also
        accepts a list of content blocks (text/image/...) for a single
        message -- used by app/routers/tutor.py when a student has
        attached a file to this turn (ADR-016, student file
        attachments). No change needed here either way: this method
        just forwards `messages` through unmodified.
        """
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
