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
from app.models import ContentChunk, Learner, Question, School, Subject, Topic, User
from app.services.auth import provision_student

DEV_LEARNER_GRADE = 10
DEV_LEARNER_NAME = "Test Learner"

# NEW 14 Nov 2026 (ADR-017, student login). Fixed, well-known values --
# never used for a real deployed school -- so local login is
# predictable across re-runs of this idempotent script.
DEV_SCHOOL_NAME = "THUTOra Demo School"
DEV_STUDENT_NUMBER = "100001"
DEV_STUDENT_PASSWORD = "DevPass123!"

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

# --- Pure Mathematics, Grade 11 (added 13 Nov 2026, ADR-014) ---
# Topic names/order follow the DBE CAPS FET Mathematics Grades 10-12 document,
# Section 3.2 (Grade 11 Annual Teaching Plan). Every Grade 11 topic maps 1:1
# by name to its Grade 10 counterpart -- the cleanest possible cross-grade
# chain (unlike Physical Sciences' cross-subject mapping). Within-grade
# prerequisites follow CAPS' own teaching order; a prerequisite entry can
# ALSO be a (subject_name, grade, topic_name) tuple instead of a plain
# string, meaning "this topic's foundation is actually in an earlier grade,
# not within this grade" -- see ADR-014 for why only the topics with no
# natural within-grade predecessor get one (Topic.prerequisite_id is a
# single self-referential FK, not a DAG with multiple parents, so each
# topic gets exactly one chain to walk, same as every subject before this).

_MATHS_GRADE11_TOPICS: list[tuple[str, "str | tuple[str, int, str] | None"]] = [
    ("Exponents and Surds", ("Pure Mathematics", 10, "Exponents")),
    ("Equations and Inequalities", "Exponents and Surds"),
    ("Number Patterns", "Equations and Inequalities"),
    ("Functions", "Equations and Inequalities"),
    ("Analytical Geometry", "Functions"),
    ("Trigonometry", "Equations and Inequalities"),
    ("Euclidean Geometry", ("Pure Mathematics", 10, "Euclidean Geometry")),
    ("Measurement", "Euclidean Geometry"),
    ("Finance, Growth and Decay", "Exponents and Surds"),
    ("Probability", ("Pure Mathematics", 10, "Probability")),
    ("Statistics", "Number Patterns"),
]

_MATHS_GRADE11_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "Exponents and Surds": [
        ("Simplify: sqrt(12) + sqrt(27)", "5*sqrt(3)"),
        ("Simplify: the cube root of 8 times the cube root of 27", "6"),
    ],
    "Equations and Inequalities": [
        ("Solve for x: x^2 - 5x + 6 = 0", "x = 2 or x = 3"),
        ("Solve for x: x^2 - x - 6 > 0", "x < -2 or x > 3"),
    ],
    "Number Patterns": [
        ("Find the next term: 1, 4, 9, 16, ...", "25"),
        ("Determine the general term for the quadratic sequence 3, 7, 13, 21, ...", "T_n = n^2 + n + 1"),
    ],
    "Functions": [
        ("Determine the x-intercepts of f(x) = x^2 - x - 6", "x = -2 or x = 3"),
        ("Describe the effect on the graph of f(x) = a*x^2 when a < 0", "The graph is reflected about the x-axis (opens downward)"),
    ],
    "Analytical Geometry": [
        ("Determine the equation of the line parallel to y = 2x + 1 passing through (3, 4)", "y = 2x - 2"),
        ("Determine whether the lines y = 2x + 1 and y = -0.5x + 3 are perpendicular", "Yes, since 2 * -0.5 = -1"),
    ],
    "Trigonometry": [
        ("Simplify: sin(180 - theta)", "sin(theta)"),
        ("Solve for theta, general solution: sin(theta) = 0.5", "theta = 30 + k*360 or theta = 150 + k*360, k an integer"),
    ],
    "Euclidean Geometry": [
        ("State the theorem relating the angle at the centre of a circle to the angle at the circumference subtended by the same arc", "The angle at the centre is twice the angle at the circumference"),
        ("AB is a diameter of a circle and C is a point on the circle. Find angle ACB", "90 degrees (angle in a semi-circle)"),
    ],
    "Measurement": [
        ("Calculate the surface area of a sphere with radius 3 cm (use pi = 3.14)", "approximately 113.04 cm^2"),
        ("Calculate the volume of a cone with radius 4 cm and height 9 cm (use pi = 3.14)", "approximately 150.72 cm^3"),
    ],
    "Finance, Growth and Decay": [
        ("Calculate the value of R5000 invested at 6% p.a. compound interest after 3 years", "R5955.08"),
        ("A car valued at R200 000 depreciates at 15% p.a. on the reducing-balance method. Find its value after 2 years", "R144 500"),
    ],
    "Probability": [
        ("A bag contains 4 red and 6 blue balls. Two balls are drawn without replacement. Find P(both red)", "(4/10)*(3/9) = 2/15"),
        ("For independent events A and B, P(A) = 0.4 and P(B) = 0.5. Find P(A and B)", "0.2"),
    ],
    "Statistics": [
        ("Calculate the variance of the data set 2, 4, 4, 4, 5, 5, 7, 9", "4"),
        ("Determine the five-number summary of 3, 7, 8, 12, 13, 14, 18, 21", "min=3, Q1=7.5, median=12.5, Q3=16, max=21"),
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
        # Added 13 Nov 2026 from a real Grade 10 Science: Electric circuits
        # revision worksheet (2014) Siya supplied -- sourced from real CAPS
        # revision content rather than synthetic examples, adapted from the
        # worksheet's own multiple-choice/fill-in format into this seed
        # script's open-question style. Answers checked against the
        # worksheet's own answer key.
        ("A simple circuit has a 24 V battery and a bulb. A current of 0.5 A flows "
         "through the bulb. Calculate how long it takes for the bulb to transfer 48 J of energy.",
         "t = W / (V*I) = 48 / (24*0.5) = 4 s"),
        ("State the name given to an object that opposes the flow of current in a circuit.",
         "A resistor"),
        ("Four 10 V cells are connected in series to form a 40 V battery. A 3 ohm resistor is "
         "connected in series with two 2 ohm resistors connected in parallel with each other. "
         "Calculate the total resistance of the circuit.",
         "R_parallel = (2*2)/(2+2) = 1 ohm; R_total = 3 + 1 = 4 ohm"),
    ],
}

# --- Physical Sciences, Grade 11 -- Physics strand only (added 13 Nov 2026, ADR-014) ---
# Topic names/order follow the DBE CAPS FET Physical Sciences Grades 10-12
# document, Section 3.2 (Grade 11 Annual Teaching Plan). Smaller than Grade 10
# (6 topics, not 8) -- the Waves/Sound/Light strand moves entirely to Grade 12.
# Unlike Grade 11 Maths, NOT every topic maps 1:1 onto a Grade 10 counterpart:
# Newton's Laws and Newton's Universal Law of Gravitation are genuinely new
# content with no Grade 10 equivalent at all, and Electromagnetism's only
# candidate Grade 10 link (Magnetism, which is purely descriptive there vs.
# quantitative flux/Faraday's-law content here) was judged too inexact to use
# as a direct cross-grade edge -- within-grade chaining only for those three.
# Only the two topics that DO have a clean, exact-name Grade 10 counterpart
# (Vectors in Two Dimensions, Electrostatics) get a cross-grade prerequisite,
# same "root topics anchor cross-grade, the rest chain within-grade" pattern
# already used for Grade 11 Pure Mathematics.

_PHYSICAL_SCIENCES_GRADE11_TOPICS: list[tuple[str, "str | tuple[str, int, str] | None"]] = [
    ("Vectors in Two Dimensions", ("Physical Sciences", 10, "Vectors in Two Dimensions")),
    ("Newton's Laws", "Vectors in Two Dimensions"),
    ("Newton's Universal Law of Gravitation", "Newton's Laws"),
    ("Electrostatics", ("Physical Sciences", 10, "Electrostatics")),
    ("Electromagnetism", "Electrostatics"),
    ("Electric Circuits", "Electromagnetism"),
]

_PHYSICAL_SCIENCES_GRADE11_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "Vectors in Two Dimensions": [
        ("Calculate the resultant of a 10 N force at 0 degrees and a 10 N force at 90 degrees",
         "14.14 N at 45 degrees"),
        ("Resolve a 20 N force acting at 60 degrees above the horizontal into its horizontal and vertical components",
         "Fx = 10 N, Fy = 17.3 N"),
    ],
    "Newton's Laws": [
        ("Calculate the net force needed to accelerate a 5 kg object at 2 m/s^2", "Fnet = ma = 10 N"),
        ("State Newton's Third Law of Motion", "For every action there is an equal and opposite reaction"),
    ],
    "Newton's Universal Law of Gravitation": [
        ("Calculate the gravitational force between two 1000 kg masses separated by 10 m (G = 6.67x10^-11 N.m^2/kg^2)",
         "F = Gm1m2/d^2 = 6.67x10^-7 N"),
        ("State Newton's Law of Universal Gravitation in words",
         "Every point mass attracts every other point mass with a force proportional to the product of "
         "their masses and inversely proportional to the square of the distance between them"),
    ],
    "Electrostatics": [
        ("Calculate the electrostatic force between two charges of 4x10^-6 C and 2x10^-6 C separated by "
         "0.2 m (k = 9x10^9 N.m^2/C^2)", "F = kq1q2/r^2 = 1.8 N"),
        ("Calculate the electric field strength 0.5 m from a point charge of 5x10^-6 C (k = 9x10^9 N.m^2/C^2)",
         "E = kQ/r^2 = 180000 N/C"),
    ],
    "Electromagnetism": [
        ("Calculate the magnetic flux through a 0.1 m^2 coil in a 0.5 T field, field perpendicular to the coil",
         "Phi = BA = 0.05 Wb"),
        ("State Lenz's Law",
         "The induced current flows in a direction that opposes the change in magnetic flux that caused it"),
    ],
    "Electric Circuits": [
        ("Calculate the terminal voltage of a battery with EMF 12 V, internal resistance 0.5 ohm, "
         "delivering a current of 2 A", "V = EMF - Ir = 11 V"),
        ("Calculate the total resistance of a 4 ohm and 6 ohm resistor connected in parallel", "R = 2.4 ohm"),
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
    {
        "name": "Pure Mathematics",
        "grade": 11,
        "topics": _MATHS_GRADE11_TOPICS,
        "questions": _MATHS_GRADE11_QUESTIONS,
    },
    {
        "name": "Physical Sciences",
        "grade": 11,
        "topics": _PHYSICAL_SCIENCES_GRADE11_TOPICS,
        "questions": _PHYSICAL_SCIENCES_GRADE11_QUESTIONS,
    },
]

# SUBJECTS order matters as of ADR-014: a topic's prerequisite can now
# reference an EARLIER subject in this list via a (subject_name, grade,
# topic_name) tuple (see _MATHS_GRADE11_TOPICS above) -- Grade 10 Pure
# Mathematics must therefore stay seeded before Grade 11 Pure Mathematics.


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


async def get_or_create_demo_school(session) -> School:
    """NEW 14 Nov 2026 (ADR-017, student login)."""
    result = await session.execute(select(School).where(School.name == DEV_SCHOOL_NAME))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing
    school = School(name=DEV_SCHOOL_NAME)
    session.add(school)
    await session.flush()
    return school


async def get_or_create_demo_student_account(session, school: School, learner: Learner) -> User:
    """
    NEW 14 Nov 2026 (ADR-017, student login). Links the dev Learner to
    a real User account for local login testing -- idempotent: if the
    learner already has a user_id (a previous run of this script), the
    existing User is reused rather than provisioning a second one.
    Uses provision_student()'s existing_learner= parameter specifically
    so this reuses the already-seeded dev Learner instead of creating a
    duplicate one -- see app/services/auth.py.
    """
    if learner.user_id is not None:
        return await session.get(User, learner.user_id)

    user, _, _ = await provision_student(
        session,
        school=school,
        display_name=learner.display_name,
        grade=learner.grade,
        student_number=DEV_STUDENT_NUMBER,
        raw_password=DEV_STUDENT_PASSWORD,
        existing_learner=learner,
    )
    return user


def _validate_subject_data(subject_spec: dict, known_subjects: set[tuple[str, int]]) -> None:
    """Fails fast on a typo'd prerequisite name/reference or a question-dict
    key that doesn't match a real topic name, instead of half-seeding the
    database.

    FIX 13 Nov 2026 (ADR-014, cross-grade prerequisites): a prerequisite can
    now be a (subject_name, grade, topic_name) tuple instead of a plain
    string, meaning "this topic's foundation is in an earlier-seeded
    subject/grade". `known_subjects` is every (name, grade) pair already
    present in SUBJECTS *before* this one -- a cross-reference to a subject
    that isn't in that set (wrong grade, typo'd name, or a subject that
    hasn't been seeded yet because it comes LATER in SUBJECTS) fails fast
    here rather than as a confusing lookup error mid-seed."""
    topics: list[tuple[str, "str | tuple[str, int, str] | None"]] = subject_spec["topics"]
    questions: dict[str, list[tuple[str, str]]] = subject_spec["questions"]
    names = {name for name, _ in topics}
    seen: set[str] = set()
    for name, prereq in topics:
        if isinstance(prereq, tuple):
            ref_subject, ref_grade, ref_topic = prereq
            if (ref_subject, ref_grade) not in known_subjects:
                raise ValueError(
                    f"[{subject_spec['name']}] Topic {name!r} names a cross-subject prerequisite "
                    f"{prereq!r}, but ({ref_subject!r}, grade {ref_grade}) isn't an earlier subject "
                    f"in SUBJECTS -- either it's a typo, or that subject needs to come BEFORE "
                    f"{subject_spec['name']!r} (grade {subject_spec['grade']}) in the SUBJECTS list."
                )
        elif prereq is not None and prereq not in seen:
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


async def _seed_subject(
    session, subject_spec: dict, all_seeded_topics: dict[tuple[str, int], dict[str, Topic]]
) -> tuple[Subject, dict[str, Topic], int, int]:
    """FIX 13 Nov 2026 (ADR-014, cross-grade prerequisites): `all_seeded_topics`
    is a running registry of every Topic seeded so far, keyed by
    (subject_name, grade) -> {topic_name: Topic} -- it's how a Grade 11
    topic resolves a prerequisite that lives back in Grade 10. Only ever
    READ here for a cross-reference, and written to once (by main(), after
    this subject's own topics_by_name is complete) so later subjects can
    reference THIS one in turn."""
    subject = await get_or_create_subject(session, subject_spec["name"], subject_spec["grade"])

    topics_by_name: dict[str, Topic] = {}
    for name, prereq in subject_spec["topics"]:
        if isinstance(prereq, tuple):
            ref_subject, ref_grade, ref_topic = prereq
            prerequisite_id = all_seeded_topics[(ref_subject, ref_grade)][ref_topic].id
        else:
            prerequisite_id = topics_by_name[prereq].id if prereq else None
        topics_by_name[name] = await get_or_create_topic(session, name, subject.id, prerequisite_id)

    questions_created = 0
    chunks_created = 0
    for name, topic in topics_by_name.items():
        questions_created += await ensure_questions(session, topic, subject_spec["questions"].get(name, []))
        chunks_created += 1 if await ensure_placeholder_content_chunk(session, topic) else 0

    return subject, topics_by_name, questions_created, chunks_created


async def main() -> None:
    # FIX 13 Nov 2026 (ADR-014, cross-grade prerequisites): validation now
    # needs to know which (subject_name, grade) pairs are seeded BEFORE
    # each subject_spec, so a cross-grade reference can be checked against
    # subjects that actually come earlier in SUBJECTS -- accumulated
    # progressively in the same order SUBJECTS (and seeding) will use.
    known_subjects: set[tuple[str, int]] = set()
    for subject_spec in SUBJECTS:
        _validate_subject_data(subject_spec, known_subjects)
        known_subjects.add((subject_spec["name"], subject_spec["grade"]))

    async with async_session_factory() as session:
        results = []
        all_seeded_topics: dict[tuple[str, int], dict[str, Topic]] = {}
        for subject_spec in SUBJECTS:
            result = await _seed_subject(session, subject_spec, all_seeded_topics)
            results.append(result)
            subject, topics_by_name, _, _ = result
            all_seeded_topics[(subject.name, subject.grade)] = topics_by_name

        learner = await get_or_create_dev_learner(session)
        demo_school = await get_or_create_demo_school(session)
        demo_user = await get_or_create_demo_student_account(session, demo_school, learner)

        await session.commit()

        for (subject, topics_by_name, questions_created, chunks_created), subject_spec in zip(
            results, SUBJECTS
        ):
            print(f"Subject: {subject.name} (grade {subject.grade}) -- id {subject.id}")
            print(f"  Topics ({len(topics_by_name)} total, {questions_created} new question(s), "
                  f"{chunks_created} new content chunk(s) this run):")
            for name, topic in topics_by_name.items():
                prereq = next((p for n, p in subject_spec["topics"] if n == name), None)
                if isinstance(prereq, tuple):
                    prereq_label = f"{prereq[2]} ({prereq[0]}, grade {prereq[1]})"
                else:
                    prereq_label = prereq or "none -- root topic"
                print(f"    - {name}  (id={topic.id}, prerequisite={prereq_label})")
            print()

        print(f"Dev learner: {learner.display_name} -- id {learner.id}")
        print()
        print("Log in at the frontend's login screen with (ADR-017):")
        print(f"  School:         {demo_school.name}  (id {demo_school.id})")
        print(f"  Student number: {demo_user.student_number}")
        print(f"  Password:       {DEV_STUDENT_PASSWORD}")
        print()
        print("Use these ids for a direct API smoke test (after logging in for a token), e.g.:")
        for subject, topics_by_name, _, _ in results:
            example_name, example_topic = next(iter(topics_by_name.items()))
            print(
                f'  topic_id   = "{example_topic.id}"   '
                f'# {subject.name} (grade {subject.grade}), topic "{example_name}" -- or any other topic above'
            )


if __name__ == "__main__":
    asyncio.run(main())
