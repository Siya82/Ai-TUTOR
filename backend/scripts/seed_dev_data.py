"""
Idempotent dev-data seed script: all seeded CAPS subjects/topics, two
diagnostic Questions per topic, one placeholder ContentChunk per topic,
and one dev Learner.

REBUILD NOTE: step 6 of REBUILD_SPEC.md's rebuild priority order,
Section 4. Deliberately ONE script rather than the original four-script
split (seed_dev_data.py / seed_additional_topics.py /
seed_more_topics.py / seed_stats_prob_measurement.py / seed_geometry.py)
-- REBUILD_SPEC.md Section 4 explicitly recommends this consolidation
over recreating the original split. content_chunks are genuine
placeholders (a short description, a zero vector) -- RAG ingestion
(scripts/ingest_content.py) was never built, see REBUILD_SPEC.md
Section 8; nothing reads these chunks yet.

FIX 12 Nov 2026 (multi-subject support, ADR-013): generalized from a
single hardcoded SUBJECT_NAME/GRADE/TOPICS/DIAGNOSTIC_QUESTIONS set to
a SUBJECTS list, each entry a self-contained subject spec, so a second
(and future) subject is "add a dict to this list", not a parallel
script or a signature change. Added CAPS Grade 10 Physical Sciences --
Physics strand only (Vectors, Mechanics, Waves, Electricity &
Magnetism) -- see ADR-013 for why the Chemistry strand (Matter &
Materials, Chemical Change, Chemical Systems) is deliberately deferred:
MathGuard verifies equation-shaped content via sympy, which fits the
Physics strand the same way it fits Maths, but most of the Chemistry
strand (classification, bonding, balancing reactions) isn't an
equation to solve in that sense -- it would ship with no real
correctness guarantee, undermining the "self-verified" differentiator
rather than extending it. Revisit once there's an actual plan for
verifying (or explicitly flagging as unverified) non-equation content.

Safe to re-run: every entity is looked up by its natural key before
being created, so running this twice does not create duplicates.

Run from backend/, with the venv active and Docker Postgres up:
    python -m scripts.seed_dev_data
"""

import asyncio

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models import ContentChunk, Learner, Question, Subject, Topic

DEV_LEARNER_GRADE = 10
DEV_LEARNER_NAME = "Test Learner"

PLACEHOLDER_EMBEDDING = [0.0] * 1536

# --- Pure Mathematics, Grade 10 (unchanged from the original single-subject seed) ---

_MATHS_TOPICS: list[tuple[str, str | None]] = [
    ("Algebraic Expressions", None),
    ("Exponents", "Algebraic Expressions"),
    ("Equations and Inequalities", "Algebraic Expressions"),
    ("Number Patterns", "Exponents"),
    ("Trigonometry", "Equations and Inequalities"),
    ("Functions", "Equations and Inequalities"),
    ("Finance, Growth and Decay", "Exponents"),
    ("Analytical Geometry", "Functions"),
    ("Euclidean Geometry", "Algebraic Expressions"),
    ("Measurement", "Euclidean Geometry"),
    ("Statistics", "Number Patterns"),
    ("Probability", "Statistics"),
]

_MATHS_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "Algebraic Expressions": [
        ("Simplify: 3x + 2x - 5", "5x - 5"),
        ("Expand: 2(x + 3)", "2x + 6"),
    ],
    "Exponents": [
        ("Simplify: 2^3 * 2^2", "2^5 = 32"),
        ("Simplify: x^5 / x^2", "x^3"),
    ],
    "Equations and Inequalities": [
        ("Solve for x: 2x + 5 = 15", "x = 5"),
        ("Solve for x: -2x > 6", "x < -3"),
    ],
    "Number Patterns": [
        ("Find the next term: 2, 5, 8, 11, ...", "14"),
        ("Find the nth-term formula for 3, 7, 11, 15, ...", "T_n = 4n - 1"),
    ],
    "Trigonometry": [
        ("Solve for theta (0 <= theta <= 90): sin(theta) = 0.5", "theta = 30 degrees"),
        ("Simplify: sin(theta) / cos(theta)", "tan(theta)"),
    ],
    "Functions": [
        ("Determine the equation of the line through (0,3) with gradient 2", "y = 2x + 3"),
        ("For f(x) = x^2 - 4, find f(2)", "f(2) = 0"),
    ],
    "Finance, Growth and Decay": [
        ("Calculate simple interest on R1000 at 5% p.a. for 2 years", "R100"),
        ("Calculate the compound amount of R1000 at 5% p.a. for 2 years", "R1102.50"),
    ],
    "Analytical Geometry": [
        ("Find the midpoint of (2,3) and (6,7)", "(4,5)"),
        ("Find the gradient between (1,2) and (3,8)", "m = 3"),
    ],
    "Euclidean Geometry": [
        ("In triangle ABC, angle A = 50 degrees and angle B = 60 degrees. Find angle C.", "70 degrees"),
        ("State the theorem about the angles opposite the equal sides of an isosceles triangle.", "They are equal"),
    ],
    "Measurement": [
        ("Calculate the area of a circle with radius 7 cm (use pi = 22/7)", "154 cm^2"),
        ("Calculate the volume of a rectangular prism 2 cm x 3 cm x 4 cm", "24 cm^3"),
    ],
    "Statistics": [
        ("Find the mean of 4, 8, 6, 10", "7"),
        ("Find the median of 3, 9, 4, 7, 2", "4"),
    ],
    "Probability": [
        ("A fair die is rolled once. What is P(rolling a 4)?", "1/6"),
        ("A bag has 3 red and 2 blue balls. What is P(red)?", "3/5"),
    ],
}

# --- Physical Sciences, Grade 10 -- Physics strand only (see module docstring) ---
# Topic names/grouping follow the DBE CAPS Grade 10 Physical Sciences document
# (sources: za.pearson.com Grade 10 Physical Sciences navigation pack;
# education.gov.za CAPS FET Physical Sciences; mathscibuddy.co.za Grade 10
# Physical Sciences past-paper topic list -- checked 12 Nov 2026).
# Three independent prerequisite sub-chains (Mechanics / Waves / Electricity),
# each rooted at None since CAPS does not sequence across them.

_PHYSICAL_SCIENCES_TOPICS: list[tuple[str, str | None]] = [
    ("Vectors in Two Dimensions", None),
    ("Motion in One Dimension", "Vectors in Two Dimensions"),
    ("Mechanical Energy", "Motion in One Dimension"),
    ("Waves, Sound and Light", None),
    ("Electromagnetic Radiation", "Waves, Sound and Light"),
    ("Magnetism", None),
    ("Electrostatics", "Magnetism"),
    ("Electric Circuits", "Electrostatics"),
]

_PHYSICAL_SCIENCES_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "Vectors in Two Dimensions": [
        ("Calculate the resultant of a 6 m displacement East and an 8 m displacement North",
         "10 m, 53.1 degrees North of East"),
        ("Find the resultant of two perpendicular forces of 3 N and 4 N", "5 N"),
    ],
    "Motion in One Dimension": [
        ("A car accelerates from rest at 2 m/s^2 for 5 s. Calculate its final velocity.",
         "v = u + at = 10 m/s"),
        ("A car travels at a constant 20 m/s for 10 s. Calculate the distance travelled.",
         "d = v*t = 200 m"),
    ],
    "Mechanical Energy": [
        ("Calculate the kinetic energy of a 2 kg object moving at 3 m/s.",
         "Ek = (1/2)mv^2 = 9 J"),
        ("Calculate the gravitational potential energy of a 5 kg object at a height of 10 m (g = 10 m/s^2).",
         "Ep = mgh = 500 J"),
    ],
    "Waves, Sound and Light": [
        ("Calculate the speed of a wave with frequency 5 Hz and wavelength 2 m.",
         "v = f*lambda = 10 m/s"),
        ("A wave has a period of 0.5 s. Calculate its frequency.", "f = 1/T = 2 Hz"),
    ],
    "Electromagnetic Radiation": [
        ("State which has the higher frequency: visible light or radio waves.", "Visible light"),
        ("List the electromagnetic spectrum in order of increasing frequency, starting with radio waves.",
         "Radio, microwave, infrared, visible light, ultraviolet, X-ray, gamma ray"),
    ],
    "Magnetism": [
        ("State what happens when two like magnetic poles are brought close together.", "They repel"),
        ("State which pole of a freely suspended bar magnet points North.", "The North-seeking pole"),
    ],
    "Electrostatics": [
        ("State whether two positive point charges attract or repel each other.", "Repel"),
        ("Calculate the electrostatic force between two charges of 2x10^-6 C and 3x10^-6 C "
         "separated by 0.1 m (k = 9x10^9 N.m^2/C^2).",
         "F = kq1q2/r^2 = 5.4 N"),
    ],
    "Electric Circuits": [
        ("Calculate the current through a 10 ohm resistor connected across a 5 V battery.",
         "I = V/R = 0.5 A"),
        ("Calculate the total resistance of two 4 ohm resistors connected in series.", "8 ohm"),
    ],
}

SUBJECTS: list[dict] = [
    {
        "name": "Pure Mathematics",
        "grade": 10,
        "topics": _MATHS_TOPICS,
        "questions": _MATHS_QUESTIONS,
    },
    {
        "name": "Physical Sciences",
        "grade": 10,
        "topics": _PHYSICAL_SCIENCES_TOPICS,
        "questions": _PHYSICAL_SCIENCES_QUESTIONS,
    },
]


async def get_or_create_subject(session, name: str, grade: int) -> Subject:
    result = await session.execute(select(Subject).where(Subject.name == name, Subject.grade == grade))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing
    subject = Subject(name=name, grade=grade)
    session.add(subject)
    await session.flush()
    return subject


async def get_or_create_topic(session, name: str, subject_id, prerequisite_id) -> Topic:
    result = await session.execute(
        select(Topic).where(Topic.subject_id == subject_id, Topic.name == name)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing
    topic = Topic(subject_id=subject_id, name=name, prerequisite_id=prerequisite_id)
    session.add(topic)
    await session.flush()
    return topic


async def ensure_questions(session, topic: Topic, pairs: list[tuple[str, str]]) -> int:
    created = 0
    for text, answer in pairs:
        result = await session.execute(
            select(Question).where(Question.topic_id == topic.id, Question.text == text)
        )
        if result.scalar_one_or_none() is not None:
            continue
        session.add(
            Question(
                topic_id=topic.id,
                text=text,
                model_answer=answer,
                is_diagnostic=True,
                is_ai_generated=False,
            )
        )
        created += 1
    if created:
        await session.flush()
    return created


async def ensure_placeholder_content_chunk(session, topic: Topic) -> bool:
    source = "placeholder (RAG ingestion not yet built, see REBUILD_SPEC.md Section 8)"
    result = await session.execute(
        select(ContentChunk).where(ContentChunk.topic_id == topic.id, ContentChunk.source == source)
    )
    if result.scalar_one_or_none() is not None:
        return False
    session.add(
        ContentChunk(
            topic_id=topic.id,
            source=source,
            text=f"Placeholder grounding text for {topic.name}. No real content has been ingested yet.",
            embedding=PLACEHOLDER_EMBEDDING,
        )
    )
    await session.flush()
    return True


async def get_or_create_dev_learner(session) -> Learner:
    result = await session.execute(select(Learner).where(Learner.display_name == DEV_LEARNER_NAME))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing
    learner = Learner(display_name=DEV_LEARNER_NAME, grade=DEV_LEARNER_GRADE, preferred_modality="balanced")
    session.add(learner)
    await session.flush()
    return learner


def _validate_subject_data(subject_spec: dict) -> None:
    """Fails fast on a typo'd prerequisite name or a question-dict key that
    doesn't match a real topic name, instead of half-seeding the database."""
    topics: list[tuple[str, str | None]] = subject_spec["topics"]
    questions: dict[str, list[tuple[str, str]]] = subject_spec["questions"]
    names = {name for name, _ in topics}
    seen: set[str] = set()
    for name, prereq in topics:
        if prereq is not None and prereq not in seen:
            raise ValueError(
                f"[{subject_spec['name']}] Topic {name!r} names prerequisite {prereq!r}, which "
                f"either doesn't exist or comes LATER in the topics list -- fix the ordering."
            )
        seen.add(name)
    unknown = set(questions) - names
    if unknown:
        raise ValueError(
            f"[{subject_spec['name']}] questions dict has keys that aren't real topic names: {unknown}"
        )


async def _seed_subject(session, subject_spec: dict) -> tuple[Subject, dict[str, Topic], int, int]:
    subject = await get_or_create_subject(session, subject_spec["name"], subject_spec["grade"])

    topics_by_name: dict[str, Topic] = {}
    for name, prereq_name in subject_spec["topics"]:
        prerequisite_id = topics_by_name[prereq_name].id if prereq_name else None
        topics_by_name[name] = await get_or_create_topic(session, name, subject.id, prerequisite_id)

    questions_created = 0
    chunks_created = 0
    for name, topic in topics_by_name.items():
        questions_created += await ensure_questions(session, topic, subject_spec["questions"].get(name, []))
        chunks_created += 1 if await ensure_placeholder_content_chunk(session, topic) else 0

    return subject, topics_by_name, questions_created, chunks_created


async def main() -> None:
    for subject_spec in SUBJECTS:
        _validate_subject_data(subject_spec)

    async with async_session_factory() as session:
        results = []
        for subject_spec in SUBJECTS:
            results.append(await _seed_subject(session, subject_spec))

        learner = await get_or_create_dev_learner(session)

        await session.commit()

        for (subject, topics_by_name, questions_created, chunks_created), subject_spec in zip(
            results, SUBJECTS
        ):
            print(f"Subject: {subject.name} (grade {subject.grade}) -- id {subject.id}")
            print(f"  Topics ({len(topics_by_name)} total, {questions_created} new question(s), "
                  f"{chunks_created} new content chunk(s) this run):")
            for name, topic in topics_by_name.items():
                prereq = next((p for n, p in subject_spec["topics"] if n == name), None)
                print(f"    - {name}  (id={topic.id}, prerequisite={prereq or 'none -- root topic'})")
            print()

        print(f"Dev learner: {learner.display_name} -- id {learner.id}")
        print()
        maths_topics = results[0][1]
        print("Use these two ids for a live POST /tutor/message smoke test (Mathematics), e.g.:")
        print(f'  learner_id = "{learner.id}"')
        print(f'  topic_id   = "{maths_topics["Equations and Inequalities"].id}"   # or any Maths topic above')
        if len(results) > 1:
            ps_topics = results[1][1]
            print()
            print("...or for Physical Sciences, e.g.:")
            print(f'  topic_id   = "{ps_topics["Motion in One Dimension"].id}"   # or any Physical Sciences topic above')


if __name__ == "__main__":
    asyncio.run(main())
