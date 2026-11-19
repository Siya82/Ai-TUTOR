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
    build_language_instructions,
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
    # FIX 15 Nov 2026 (ADR-027, dev/admin diagnosis bypass). Siya's
    # dev/admin account (Learner.skip_diagnosis=True, set only by
    # seed_dev_data.py's get_or_create_dev_learner()) has zero real
    # attempt history on anything, so the real diagnose_root_gap() walk
    # would ALWAYS redirect it to the deepest foundational prerequisite
    # in any chain -- "treat this profile as already having met all the
    # other grades' requirements" (Siya's own words) means asking about
    # a Grade 12 topic should teach Grade 12 directly, every time, not
    # cascade down to Grade 10/11. diagnosis.py itself is NOT touched --
    # the real mastery-redirect logic (ADR-007, a protected differentiator
    # per ADR-011) stays fully intact for every real student; this is a
    # per-learner, explicitly flagged bypass at the orchestration layer
    # only, read straight off the already-loaded Learner object -- no
    # new DB call, so this function's DB-free contract still holds.
    if learner.skip_diagnosis:
        diagnosis = DiagnosisResult(
            recommended_topic=prerequisite_chain[0], redirected=False, steps=[]
        )
    else:
        diagnosis = diagnose_root_gap(prerequisite_chain, attempts_by_topic)
    recommended_topic = diagnosis.recommended_topic

    modality = learner.preferred_modality
    if modality not in VALID_MODALITIES:
        modality = DEFAULT_MODALITY

    pace_tier = compute_pace_tier(attempts_by_topic.get(recommended_topic.id, []))
    personalization_block = build_personalization_instructions(modality, pace_tier)
    # NEW 19 Nov 2026 (ADR-035): optional home-language bridging.
    personalization_block += build_language_instructions(getattr(learner, "home_language", None))

    diagnosis_note = None
    if diagnosis.redirected:
        requested_topic = prerequisite_chain[0]

        # FIX 15 Nov 2026 (grade-context in redirects): the learner should
        # be told WHICH GRADE the foundational gap belongs to, not just its
        # name -- otherwise a Grade 12 question silently teaching Grade 10
        # content reads as a non-sequitur. diagnosis.steps is already in
        # prerequisite_chain order (requested topic first, deepest last);
        # diagnose_root_gap() breaks immediately after at most one
        # "confirmed_mastery" step, so excluding that status leaves exactly
        # the real gap chain from what was asked down to recommended_topic
        # (inclusive). Each Topic's .subject must already be eager-loaded
        # by the caller, same requirement as recommended_topic.subject
        # below -- this stays DB-free.
        topics_by_id = {topic.id: topic for topic in prerequisite_chain}
        gap_chain = [
            topics_by_id[step.topic_id]
            for step in diagnosis.steps
            if step.status != "confirmed_mastery"
        ]
        grade_chain_text = " -> ".join(
            f"'{topic.name}' (Grade {topic.subject.grade} {topic.subject.name})"
            for topic in gap_chain
        )
        diagnosis_note = (
            f"DIAGNOSIS NOTE: the learner asked a Grade {requested_topic.subject.grade} "
            f"question about '{requested_topic.name}', but their recent attempt history "
            f"shows a gap at the more foundational topic '{recommended_topic.name}' "
            f"(Grade {recommended_topic.subject.grade}). The full gap chain, from what they "
            f"asked to where teaching should actually start, is: {grade_chain_text}. Before "
            f"teaching, explain this redirect in ONE encouraging sentence that EXPLICITLY "
            f"names the grade level(s) involved -- e.g. tell the learner this question "
            f"depends on a Grade {recommended_topic.subject.grade} skill they should have "
            f"covered before tackling Grade {requested_topic.subject.grade} work (frame it as "
            f"strengthening the foundation first, not as a failure), then teach "
            f"'{recommended_topic.name}'."
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
