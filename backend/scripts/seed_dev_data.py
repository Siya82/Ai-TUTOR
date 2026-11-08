"""
Idempotent dev-data seed script: all 12 CAPS Grade 10 Pure Mathematics
topics, chained back to Algebraic Expressions via Topic.prerequisite_id,
two diagnostic Questions per topic, one placeholder ContentChunk per
topic, and one dev Learner.

REBUILD NOTE: step 6 of REBUILD_SPEC.md's rebuild priority order,
Section 4. Deliberately ONE script rather than the original four-script
split (seed_dev_data.py / seed_additional_topics.py /
seed_more_topics.py / seed_stats_prob_measurement.py / seed_geometry.py)
-- REBUILD_SPEC.md Section 4 explicitly recommends this consolidation
over recreating the original split. content_chunks are genuine
placeholders (a short description, a zero vector) -- RAG ingestion
(scripts/ingest_content.py) was never built, see REBUILD_SPEC.md
Section 8; nothing reads these chunks yet.

Safe to re-run: every entity is looked up by its natural key before
being created, so running this twice does not create duplicates.

Run from backend/, with the venv active and Docker Postgres up:
    python -m scripts.seed_dev_data
"""

import asyncio

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models import ContentChunk, Learner, Question, Subject, Topic

SUBJECT_NAME = "Pure Mathematics"
GRADE = 10

PLACEHOLDER_EMBEDDING = [0.0] * 1536

# (topic name, prerequisite topic name or None for the root). Order matters:
# every prerequisite must appear earlier in this list than the topic that
# names it, since topics are created in this order and need a real
# (already-flushed) prerequisite id to point at.
TOPICS: list[tuple[str, str | None]] = [
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

# Two diagnostic questions per topic: (question text, model answer).
DIAGNOSTIC_QUESTIONS: dict[str, list[tuple[str, str]]] = {
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

DEV_LEARNER_NAME = "Test Learner"


async def get_or_create_subject(session) -> Subject:
    result = await session.execute(
        select(Subject).where(Subject.name == SUBJECT_NAME, Subject.grade == GRADE)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing
    subject = Subject(name=SUBJECT_NAME, grade=GRADE)
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
    learner = Learner(display_name=DEV_LEARNER_NAME, grade=GRADE, preferred_modality="balanced")
    session.add(learner)
    await session.flush()
    return learner


def _validate_topic_data() -> None:
    """Fails fast on a typo'd prerequisite name or a question-dict key that
    doesn't match a real topic name, instead of half-seeding the database."""
    names = {name for name, _ in TOPICS}
    seen: set[str] = set()
    for name, prereq in TOPICS:
        if prereq is not None and prereq not in seen:
            raise ValueError(
                f"Topic {name!r} names prerequisite {prereq!r}, which either doesn't exist "
                f"or comes LATER in the TOPICS list -- fix the ordering."
            )
        seen.add(name)
    unknown = set(DIAGNOSTIC_QUESTIONS) - names
    if unknown:
        raise ValueError(f"DIAGNOSTIC_QUESTIONS has keys that aren't real topic names: {unknown}")


async def main() -> None:
    _validate_topic_data()

    async with async_session_factory() as session:
        subject = await get_or_create_subject(session)

        topics_by_name: dict[str, Topic] = {}
        for name, prereq_name in TOPICS:
            prerequisite_id = topics_by_name[prereq_name].id if prereq_name else None
            topics_by_name[name] = await get_or_create_topic(session, name, subject.id, prerequisite_id)

        questions_created = 0
        chunks_created = 0
        for name, topic in topics_by_name.items():
            questions_created += await ensure_questions(session, topic, DIAGNOSTIC_QUESTIONS.get(name, []))
            chunks_created += 1 if await ensure_placeholder_content_chunk(session, topic) else 0

        learner = await get_or_create_dev_learner(session)

        await session.commit()

        print(f"Subject: {subject.name} (grade {subject.grade}) -- id {subject.id}")
        print(f"Topics ({len(topics_by_name)} total, {questions_created} new question(s), "
              f"{chunks_created} new content chunk(s) this run):")
        for name, topic in topics_by_name.items():
            prereq = next((p for n, p in TOPICS if n == name), None)
            print(f"  - {name}  (id={topic.id}, prerequisite={prereq or 'none -- root topic'})")
        print(f"Dev learner: {learner.display_name} -- id {learner.id}")
        print()
        print("Use these two ids for a live POST /tutor/message smoke test, e.g.:")
        print(f'  learner_id = "{learner.id}"')
        print(f'  topic_id   = "{topics_by_name["Equations and Inequalities"].id}"   # or any topic above')


if __name__ == "__main__":
    asyncio.run(main())
