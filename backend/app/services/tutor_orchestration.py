"""
prepare_tutor_turn(): the pure, DB-free orchestration step between a
tutor request and the actual Claude call -- diagnosis, then
personalization, then prompt assembly. See REBUILD_SPEC.md Section 1.

REBUILD NOTE: rebuilt from REBUILD_SPEC.md Section 1 -- not recovered
code.

FIX 12 Nov 2026 (multi-subject support, ADR-013): now reads
recommended_topic.subject.name/.grade to build a subject-aware system
prompt (see tutor.py's own fix note). Since this module is deliberately
DB-free, it requires the caller to have already eager-loaded
Topic.subject -- it does not, and must not, trigger a lazy load itself.

FIX 14 Nov 2026 (ADR-021, real RAG content grounding): prepare_tutor_turn()
now takes an optional grounding_text, forwarded straight through to
build_tutor_system_prompt(). This module stays deliberately DB-free --
fetching grounding_text (which needs both a DB query and an embeddings
API call, see app/services/retrieval.py) is the caller's job
(routers/tutor.py), done via a second, cheap call to diagnose_root_gap()
before this function runs, so the caller knows which topic will
actually be taught in time to look up its grounding. See
routers/tutor.py's own comment on that doubled call.
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
    grounding_text: str | None = None,
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

    # FIX 12 Nov 2026 (multi-subject support, ADR-013): recommended_topic.subject
    # must already be eager-loaded by the caller (routers/tutor.py uses
    # selectinload(Topic.subject) on every Topic it fetches) -- this module
    # stays DB-free per its own docstring, so it cannot lazy-load it itself.
    system_prompt = build_tutor_system_prompt(
        topic_name=recommended_topic.name,
        personalization_block=personalization_block,
        subject_name=recommended_topic.subject.name,
        grade=recommended_topic.subject.grade,
        diagnosis_note=diagnosis_note,
        grounding_text=grounding_text,
    )

    return TutorTurnPrep(
        system_prompt=system_prompt,
        recommended_topic=recommended_topic,
        diagnosis=diagnosis,
        modality_used=modality,
        pace_tier=pace_tier,
    )
