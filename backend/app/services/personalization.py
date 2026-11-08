"""
Personalization: learner-chosen presentation preference + a continuously
re-derived adaptive pace tier. See docs/ADR-002-personalization.md.

REBUILD NOTE: rebuilt from REBUILD_SPEC.md Section 1 plus ADR-002 -- not
recovered code. The pace-tier accuracy cut points below
(NEEDS_SUPPORT_MAX_ACCURACY, READY_FOR_EXTENSION_MIN_ACCURACY) are this
rebuild's own reasonable choice, not recovered values -- tune them
against real learner data once there is any. The allowed
preferred_modality values ("visual" | "practical" | "auditory" |
"balanced") ARE recovered, from the comment on
Learner.preferred_modality in app/models/__init__.py.
"""

from datetime import UTC, datetime, timedelta

from app.models import Attempt

RECENT_WINDOW_DAYS = 14
MIN_ATTEMPTS_FOR_PACE_SIGNAL = 3

NEEDS_SUPPORT_MAX_ACCURACY = 0.5
READY_FOR_EXTENSION_MIN_ACCURACY = 0.85

VALID_MODALITIES = {"visual", "practical", "auditory", "balanced"}
DEFAULT_MODALITY = "balanced"

_MODALITY_PROMPT_TEXT = {
    "visual": (
        "This learner prefers visual explanations -- favour diagrams, graphs, and spatial "
        "descriptions where the medium allows it, and describe visual structure in words "
        "when it doesn't."
    ),
    "practical": (
        "This learner prefers practical, real-world-grounded explanations -- anchor abstract "
        "steps to a concrete real-world scenario wherever natural."
    ),
    "auditory": (
        "This learner prefers explanations that read naturally out loud -- favour clear "
        "spoken rhythm and verbal signposting ('first... then... finally...') over dense "
        "notation."
    ),
    "balanced": (
        "This learner has no stated presentation preference -- use a balanced mix of worked "
        "symbolic steps and plain-language explanation."
    ),
}

_PACE_PROMPT_TEXT = {
    "needs_support": (
        "This learner's recent accuracy on this topic is low. Slow down: show every "
        "intermediate step explicitly, check understanding before moving on, and prefer "
        "simpler numbers in any example you add."
    ),
    "on_pace": (
        "This learner's recent accuracy on this topic is solid. Teach at a normal pace with "
        "the usual level of step detail."
    ),
    "ready_for_extension": (
        "This learner's recent accuracy on this topic is strong. Keep the core explanation "
        "concise and offer a brief extension or a slightly harder follow-up question rather "
        "than over-explaining the basics."
    ),
}


def _now_naive() -> datetime:
    # Attempt.created_at is a naive datetime.utcnow() default (see
    # app/models/__init__.py) -- comparing a timezone-aware "now" against
    # it would raise. datetime.now(UTC) is used instead of the deprecated
    # datetime.utcnow() (per ADR-010), then made naive to match, rather
    # than migrating the whole schema to aware datetimes in this pass.
    return datetime.now(UTC).replace(tzinfo=None)


def compute_pace_tier(attempts: list[Attempt], now: datetime | None = None) -> str:
    """
    Looks at a learner's attempts on ONE topic from the last
    RECENT_WINDOW_DAYS days and returns "needs_support" / "on_pace" /
    "ready_for_extension" based on accuracy. Defaults to "on_pace" if
    fewer than MIN_ATTEMPTS_FOR_PACE_SIGNAL recent, scored attempts exist
    -- too little signal to adapt on. Attempts older than the window, or
    not yet scored (is_correct is None), are excluded.
    """
    now = now or _now_naive()
    cutoff = now - timedelta(days=RECENT_WINDOW_DAYS)

    recent_scored = [
        a for a in attempts
        if a.is_correct is not None and a.created_at >= cutoff
    ]

    if len(recent_scored) < MIN_ATTEMPTS_FOR_PACE_SIGNAL:
        return "on_pace"

    accuracy = sum(1 for a in recent_scored if a.is_correct) / len(recent_scored)

    if accuracy <= NEEDS_SUPPORT_MAX_ACCURACY:
        return "needs_support"
    if accuracy >= READY_FOR_EXTENSION_MIN_ACCURACY:
        return "ready_for_extension"
    return "on_pace"


def build_personalization_instructions(modality: str, pace_tier: str) -> str:
    """
    Turns a (validated) modality + pace tier into a standalone
    system-prompt block, kept separate from the core CAPS-grounding
    prompt in tutor.py so it's independently testable (ADR-002,
    REBUILD_SPEC.md Section 1). Unknown values fall back to the default
    modality / "on_pace" rather than raising -- callers are expected to
    validate modality themselves (see tutor_orchestration.py), but this
    stays defensive on its own.
    """
    modality_text = _MODALITY_PROMPT_TEXT.get(modality, _MODALITY_PROMPT_TEXT[DEFAULT_MODALITY])
    pace_text = _PACE_PROMPT_TEXT.get(pace_tier, _PACE_PROMPT_TEXT["on_pace"])
    return f"{modality_text}\n{pace_text}"
