"""
prepare_tutor_turn(): the pure, DB-free orchestration step between a
tutor request and the actual Claude call -- diagnosis, then
personalization, then prompt assembly. See REBUILD_SPEC.md Section 1.

REBUILD NOTE: rebuilt from REBUILD_SPEC.md Section 1 -- not recovered
code.
"""

import uuid
from dataclasses import dataclass

from app.models import Attempt, Learner, Topic
from app.services.diagnosis import DiagnosisResult, diagnose_root_gap
from app.services.personalization import (
    DEFAULT_MODALITY,
    VALID_MODALITIES,
    build_personalization_instructions,
    compute_pace_tier,
)
from app.services.tutor import build_tutor_system_prompt


@dataclass
class TutorTurnPrep:
    system_prompt: str
    recommended_topic: Topic
    diagnosis: DiagnosisResult
    modality_used: str
    pace_tier: str


def prepare_tutor_turn(
    learner: Learner,
    prerequisite_chain: list[Topic],
    attempts_by_topic: dict[uuid.UUID, list[Attempt]],
) -> TutorTurnPrep:
    """
    prerequisite_chain[0] is the topic the learner actually asked about;
    the rest are its resolved prerequisites, deepest last (see
    diagnosis.diagnose_root_gap for how the chain should be ordered).

    Order of operations (REBUILD_SPEC.md Section 1):
    1. Run diagnose_root_gap() first -- it may recommend teaching a
       different (more foundational) topic than the one requested.
    2. Build the personalization instructions for whichever topic is
       actually going to be taught.
    3. Build the full tutor system prompt grounded on that topic, with
       an explicit diagnosis note when a redirect happened, instructing
       the tutor to explain the redirect in one encouraging sentence
       before teaching.

    Falls back to the "balanced" modality, rather than crashing, if the
    learner record has an invalid or legacy preferred_modality value.
    """
    diagnosis = diagnose_root_gap(prerequisite_chain, attempts_by_topic)
    recommended_topic = diagnosis.recommended_topic

    modality = learner.preferred_modality
    if modality not in VALID_MODALITIES:
        modality = DEFAULT_MODALITY

    pace_tier = compute_pace_tier(attempts_by_topic.get(recommended_topic.id, []))
    personalization_block = build_personalization_instructions(modality, pace_tier)

    diagnosis_note = None
    if diagnosis.redirected:
        requested_topic = prerequisite_chain[0]
        diagnosis_note = (
            f"DIAGNOSIS NOTE: the learner asked about '{requested_topic.name}', but their "
            f"recent attempt history shows a gap at the more foundational topic "
            f"'{recommended_topic.name}'. Before teaching, explain this redirect in ONE "
            f"encouraging sentence (frame it as strengthening the foundation first, not as a "
            f"failure), then teach '{recommended_topic.name}'."
        )

    system_prompt = build_tutor_system_prompt(
        topic_name=recommended_topic.name,
        personalization_block=personalization_block,
        diagnosis_note=diagnosis_note,
    )

    return TutorTurnPrep(
        system_prompt=system_prompt,
        recommended_topic=recommended_topic,
        diagnosis=diagnosis,
        modality_used=modality,
        pace_tier=pace_tier,
    )
