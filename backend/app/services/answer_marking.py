"""
AI-marking for assignment answers. See docs/ADR-028-assignments.md.

NEW 15 Nov 2026 (ADR-028, assignments). This is the first code in the
app that turns a learner's raw response into a scored Attempt -- see
ADR-028's Context section for the finding that no Attempt row has ever
actually been written in production before this. Deliberately reuses
TutorClient.ask() (app/services/tutor.py) rather than standing up a
second Claude integration: marking is just a different, narrower
system prompt against the same client.
"""

import json
import re
from dataclasses import dataclass

from app.services.tutor import TutorClient

_MARKING_SYSTEM_PROMPT_TEMPLATE = """\
You are marking a single student answer against a model answer. Be strict \
but fair: award correctness for mathematically or substantively equivalent \
answers even if the wording, formatting, or order of steps differs from the \
model answer. A minor arithmetic slip that changes the final answer should \
still be marked incorrect.

Question:
{question_text}

Model answer:
{model_answer}

Student's answer:
{learner_response}

Respond with ONLY a JSON object, no other text before or after it, in \
exactly this shape:
{{"is_correct": true or false, "feedback": "one or two sentences of \
feedback for the student, explaining what was right or wrong"}}
"""

# Claude sometimes wraps JSON in a ```json ... ``` fence despite being told
# not to -- strip it rather than fail marking over a formatting quirk.
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass
class MarkingResult:
    # None means marking failed or was unparseable -- "unmarked", never a
    # guessed True or False. See mark_answer()'s docstring for why.
    is_correct: bool | None
    feedback: str | None


async def mark_answer(
    tutor_client: TutorClient,
    *,
    question_text: str,
    model_answer: str,
    learner_response: str,
) -> MarkingResult:
    """
    Ask Claude to mark a single learner_response against model_answer,
    via the same TutorClient used for ordinary tutoring turns -- a
    different system prompt, not a second integration.

    Malformed, non-JSON, or API-failure output degrades to
    MarkingResult(is_correct=None, ...) -- "unmarked" -- rather than
    guessing True or False, per ADR-028: a wrong guess here would
    silently corrupt the Attempt row and everything downstream that
    reads it (diagnosis.py, personalization.py, dashboard.py,
    risk_assessment.py), whereas is_correct=None is visibly incomplete
    and can be re-marked or reviewed by a teacher later.
    """
    system_prompt = _MARKING_SYSTEM_PROMPT_TEMPLATE.format(
        question_text=question_text,
        model_answer=model_answer,
        learner_response=learner_response,
    )
    try:
        # max_tokens 600 (ADR-035): a verdict plus a few sentences of
        # feedback never needs the tutor's 2048.
        raw = await tutor_client.ask(
            system_prompt, [{"role": "user", "content": "Mark this answer."}], max_tokens=600
        )
    except Exception as exc:  # noqa: BLE001 -- any API failure degrades to unmarked
        return MarkingResult(
            is_correct=None, feedback=f"Marking failed (API error): {exc}"
        )

    cleaned = _JSON_FENCE_RE.sub("", raw.strip()).strip()
    try:
        parsed = json.loads(cleaned)
        is_correct = parsed["is_correct"]
        feedback = parsed.get("feedback")
        if not isinstance(is_correct, bool):
            raise ValueError("is_correct was not a JSON boolean")
    except (json.JSONDecodeError, KeyError, ValueError):
        return MarkingResult(
            is_correct=None,
            feedback=(
                "Could not automatically mark this answer -- "
                "a teacher may need to review it."
            ),
        )

    return MarkingResult(is_correct=is_correct, feedback=feedback)
