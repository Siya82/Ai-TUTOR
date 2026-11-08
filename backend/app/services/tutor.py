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
"""

from anthropic import AsyncAnthropic

from app.core.config import settings

# Raised from 1024 to 2048 per ADR-010, to reduce truncation risk on
# longer, multi-step explanations.
MAX_TOKENS = 2048

_WORKED_EXAMPLE_ANCHOR = """\
Calibration example -- match THIS depth of explanation on every problem, not just this one:

Problem: Solve for x: 2x + 5 = 15
Step 1: Subtract 5 from both sides: 2x = 10
  Why this is valid: subtracting the same value from both sides preserves equality -- \
whatever you do to one side of an equation, you must do to the other, or it stops being a \
true statement.
Step 2: Divide both sides by 2: x = 5
  Why this is valid: dividing both sides by the same non-zero number also preserves \
equality, and dividing the coefficient of x by itself is exactly what isolates x.\
"""

_EXPLAIN_WHY_RULE = """\
NON-NEGOTIABLE RULE: for every transformation or step you show, you must explain WHY it is \
valid -- not just state what the step is. A learner who only sees "what happened" without \
"why it's allowed" has not been taught, even if the arithmetic is correct. If a learner asks \
"why?" again about something you already explained, re-explain it differently (do not repeat \
the same wording), and consider whether they are actually asking about a more foundational \
concept underneath the one you just covered.\
"""

_RAG_GROUNDING_PLACEHOLDER = """\
[CAPS content grounding: not yet wired to real retrieval -- content_chunks ingestion is a \
known placeholder, see REBUILD_SPEC.md Section 8. Answer from general CAPS Grade 10 \
Mathematics curriculum knowledge until this is implemented.]\
"""


def build_tutor_system_prompt(
    topic_name: str,
    personalization_block: str,
    diagnosis_note: str | None = None,
) -> str:
    """
    Builds the full tutor system prompt. Always includes, in order: a
    short framing line naming the topic, the worked-example calibration
    anchor, the non-negotiable "explain why" rule, the RAG-grounding
    placeholder block, an optional diagnosis note (present only when
    tutor_orchestration.prepare_tutor_turn() redirected teaching to a
    prerequisite topic), and the personalization block from
    personalization.py.
    """
    sections = [
        f"You are THUTOra, a CAPS-aligned Grade 10 Mathematics tutor. The current topic is: "
        f"{topic_name}.",
        _WORKED_EXAMPLE_ANCHOR,
        _EXPLAIN_WHY_RULE,
        _RAG_GROUNDING_PLACEHOLDER,
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
        messages: a list of {"role": "user" | "assistant", "content": str}
        dicts, in order -- NOT including the system prompt. Anthropic's
        API takes the system prompt via the dedicated `system` parameter
        rather than a {"role": "system"} message in `messages`, which it
        does not accept (ADR-010).
        """
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
