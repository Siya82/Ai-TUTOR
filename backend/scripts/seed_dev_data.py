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

from app.core.config import settings
from app.core.database import async_session_factory
from app.models import (
    Circuit,
    District,
    OfficialAssignment,
    ParentLink,
    ClassMember,
    ContentChunk,
    Learner,
    Question,
    School,
    SchoolClass,
    StaffRole,
    Subject,
    TeachingAllocation,
    Topic,
    User,
)
from app.services.auth import hash_password, provision_student, provision_teacher

# FIX 15 Nov 2026 (ADR-026 follow-up): was 10. Siya's own dev/test
# account is the one he uses to troubleshoot LEARN across every grade,
# not a stand-in for a typical Grade 10 student -- ADR-026's new
# Subject.grade <= learner.grade filter means whatever grade this
# constant holds is the ceiling of what this account can see. 12 is
# CAPS' own terminal grade (there is no Grade 13), so this is the
# highest value that still means anything -- it gives this one account
# every seeded grade, not an arbitrary bump.
DEV_LEARNER_GRADE = 12
DEV_LEARNER_NAME = "Test Learner"

# NEW 14 Nov 2026 (ADR-017, student login). Fixed, well-known values --
# never used for a real deployed school -- so local login is
# predictable across re-runs of this idempotent script.
DEV_SCHOOL_NAME = "THUTOra Demo School"
DEV_STUDENT_NUMBER = "100001"
# NEW 15 Nov 2026 (ADR-024, teacher dashboard access + bulk student
# provisioning). There is still no in-product way to create a school's
# FIRST teacher account (ADR-017's "no self-service signup" stance
# applies to teachers too) -- this script remains the only way, same
# as it was the only way to log in as a student before this script
# existed to provision one.
DEV_TEACHER_NUMBER = "T00001"
DEV_STUDENT_PASSWORD = "DevPass123!"
# NEW 15 Nov 2026 (live-test convenience). Deliberately the SAME value as
# DEV_STUDENT_PASSWORD, not a separate password -- Siya asked to use one
# password across every THUTOra role while live-testing by hand. The LOGIN
# NUMBER still can't be shared: student_number doubles as the login
# identifier for every role and is uniquely constrained per school
# regardless of role (uq_user_school_student_number on (school_id,
# student_number)), so a teacher and a student in the same school can
# never carry the same number -- that is a real collision, not a style
# choice, and changing it would mean loosening a schema constraint that
# exists to catch a real school accidentally issuing one number twice.
DEV_TEACHER_PASSWORD = DEV_STUDENT_PASSWORD
# NEW 17 Nov 2026 (ADR-031, school roles and scoping). A staff account now
# sees nothing without an allocation or role, so the dev school gets:
#   - T00001 "Dev Teacher": teaches Pure Mathematics (Grade 12) to class 12A,
#     which contains the dev learner (100001, Grade 12)
#   - P00001 "Dev Principal": principal role, whole school
DEV_PRINCIPAL_NUMBER = "P00001"
DEV_CLASS_NAME = "12A"
DEV_ALLOCATION_SUBJECT = ("Pure Mathematics", 12)

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

# --- Accounting, Grade 10 (added 14 Nov 2026, ADR-018) ---
# Topic names/order follow the DBE CAPS Grade 10 Accounting Annual Teaching
# Plan (education.gov.za) and the Via Afrika Grade 10 Accounting Study Guide's
# topic breakdown (checked 14 Nov 2026) -- the full Grade 10 scope, not a
# narrowed subset: unlike Physical Sciences' Physics-strand-only cut (ADR-013),
# there is no equation-shaped/non-equation-shaped split clean enough to carve
# out a worse-coverage subset of Accounting itself. What IS narrowed, and
# explicitly flagged in ADR-018, is verification: MathGuard's sympy-based
# equation-solving doesn't apply to most of this content as-is (a trial
# balance "balancing" or a ledger account's running balance isn't the same
# verification shape as "solve this equation for x"), so these topics are
# taught WITHOUT math_verified-style checking for now -- same "honest,
# permanent-until-revisited limitation" posture Euclidean Geometry proofs
# already have, not silently claimed as verified. A handful of topics
# (Accounting Equation, VAT, Trial Balance) genuinely ARE numeric-equality
# checks a future accounting-specific verifier could cover -- see ADR-018's
# open-items list.
#
# One linear backbone (Concepts -> Equation -> Cash Journals -> Credit
# Journals -> Ledger/Trial Balance) matching the CAPS Term 1 teaching order,
# then three branches off the Ledger/Trial Balance topic for Term 2 content
# (VAT, Salaries and Wages, and Year-End Adjustments chained off Salaries) --
# same "shared trunk, multiple branches" shape Grade 10 Maths already uses
# off Algebraic Expressions.

_ACCOUNTING_TOPICS: list[tuple[str, str | None]] = [
    ("Accounting Concepts, GAAP and Internal Control", None),
    ("The Accounting Equation", "Accounting Concepts, GAAP and Internal Control"),
    ("Cash Journals (CRJ, CPJ, PCJ)", "The Accounting Equation"),
    ("Credit Journals (DJ, DAJ, CJ, CAJ, GJ)", "Cash Journals (CRJ, CPJ, PCJ)"),
    ("General Ledger and Trial Balance", "Credit Journals (DJ, DAJ, CJ, CAJ, GJ)"),
    ("Value-Added Tax (VAT)", "General Ledger and Trial Balance"),
    ("Salaries and Wages", "General Ledger and Trial Balance"),
    ("Year-End Adjustments", "Salaries and Wages"),
    ("Financial Statements (Income Statement and Balance Sheet)", "Year-End Adjustments"),
    ("Budgeting (Cash Budget)", "Value-Added Tax (VAT)"),
]

_ACCOUNTING_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "Accounting Concepts, GAAP and Internal Control": [
        ("Name the GAAP principle that requires a business's financial affairs "
         "to be kept completely separate from the owner's personal affairs.",
         "The business entity principle (business entity concept/rule)"),
        ("Give one example of an internal control measure a business can use "
         "to protect its cash.",
         "E.g. requiring two authorised signatures on cheques, or separating the "
         "duties of the person who handles cash from the person who records it"),
    ],
    "The Accounting Equation": [
        ("A business has Assets of R85 000 and Liabilities of R25 000. Use the "
         "accounting equation to calculate Owner's Equity.",
         "Owner's Equity = R60 000 (A = OE + L, so OE = A - L = 85 000 - 25 000)"),
        ("The owner deposits R10 000 of her own cash into the business bank "
         "account. State the effect of this transaction on the accounting equation.",
         "Assets (Bank) increase by R10 000 and Owner's Equity (Capital) increases "
         "by R10 000 -- the equation stays balanced"),
    ],
    "Cash Journals (CRJ, CPJ, PCJ)": [
        ("In which journal would a cash sale be recorded?",
         "The Cash Receipts Journal (CRJ)"),
        ("In which journal would a small cash payment for stationery, paid out "
         "of petty cash, be recorded?",
         "The Petty Cash Journal (PCJ)"),
    ],
    "Credit Journals (DJ, DAJ, CJ, CAJ, GJ)": [
        ("In which journal would goods sold on credit to a debtor be recorded?",
         "The Debtors Journal (DJ)"),
        ("A debtor returns damaged goods that were originally sold to them on "
         "credit. Which journal is used to record this?",
         "The Debtors Allowances Journal (DAJ)"),
    ],
    "General Ledger and Trial Balance": [
        ("What must always be true of the total debit column and the total "
         "credit column of a correctly prepared Trial Balance?",
         "They must be equal"),
        ("A Trial Balance's debit column totals R142 500 and its credit column "
         "totals R138 900. What does this tell you?",
         "The trial balance does not balance, so there is an error somewhere in "
         "the ledger -- a posting is missing, duplicated, or on the wrong side"),
    ],
    "Value-Added Tax (VAT)": [
        ("Calculate the VAT amount on goods sold for R1 000 (VAT-exclusive), "
         "with VAT at 15%.",
         "R150 (1000 * 0.15)"),
        ("Goods are sold for a VAT-inclusive price of R1 150, with VAT at 15%. "
         "Calculate the VAT-exclusive price.",
         "R1 000 (1150 / 1.15)"),
    ],
    "Salaries and Wages": [
        ("Name two deductions that are typically subtracted from an employee's "
         "gross salary to arrive at their net salary.",
         "E.g. PAYE (income tax) and UIF (Unemployment Insurance Fund) contributions"),
        ("An employee's gross salary is R12 000 and total deductions are "
         "R2 400. Calculate the employee's net salary.",
         "R9 600 (12 000 - 2 400)"),
    ],
    "Year-End Adjustments": [
        ("At year-end, R500 of stationery bought during the year has not yet "
         "been used. What type of adjustment is required?",
         "A consumable stores on hand adjustment -- the unused stationery is an "
         "asset, not yet an expense, until it is actually used"),
        ("Rent income of R1 200 was received in advance for the next financial "
         "year. Name the adjustment this requires.",
         "Income received in advance (a liability) -- the R1 200 must be removed "
         "from this year's rent income and carried over to next year"),
    ],
    "Financial Statements (Income Statement and Balance Sheet)": [
        ("Which financial statement shows a business's income and expenses "
         "for a financial period?",
         "The Income Statement (Statement of Comprehensive Income)"),
        ("Which financial statement shows a business's assets, liabilities, "
         "and owner's equity at a specific point in time?",
         "The Balance Sheet (Statement of Financial Position)"),
    ],
    "Budgeting (Cash Budget)": [
        ("What is the main purpose of preparing a Cash Budget?",
         "To plan and predict a business's expected cash receipts and cash "
         "payments over a future period, so it can manage its cash flow"),
        ("A business expects cash receipts of R45 000 and cash payments of "
         "R52 000 for a month. Calculate the expected cash surplus or shortfall.",
         "A shortfall (deficit) of R7 000 (45 000 - 52 000 = -7 000)"),
    ],
}

# --- Accounting, Grade 11 (added 14 Nov 2026, ADR-019) ---
# Topic names/order follow the DBE CAPS Grade 11 Accounting Annual Teaching
# Plan (education.gov.za, checked 14 Nov 2026). Unlike Grade 11 Pure
# Mathematics' clean 1:1 name mapping (ADR-014), most of Grade 11 Accounting
# is genuinely new content (a partnership is a different business entity
# from Grade 10's sole trader; ratio analysis and manufacturing costing don't
# exist in Grade 10 at all) -- closer in shape to Grade 11 Physical Sciences
# (ADR-015), where only some topics got an exact-name cross-grade anchor.
#
# Four independent branches, each rooted in its OWN Grade 10 Accounting
# topic (not one shared Grade 10 trunk, unlike Grade 10 Accounting's own
# single-trunk-with-branches shape) -- see ADR-019 for why each cross-grade
# root was chosen (a real prerequisite skill, not a same-grade coincidence)
# and why Fixed Assets deliberately does NOT get a cross-grade anchor (no
# clean Grade 10 counterpart exists for depreciation/asset-register content,
# same "don't force an inexact mapping" judgment call ADR-015 made for
# Electromagnetism/Magnetism).
#
# "Budgeting (Cash Budget)" and "Value-Added Tax (VAT)" reuse their exact
# Grade 10 names (same convention Maths/Physical Sciences already use for a
# deepened skill) -- this also means SymbolKeyboard.jsx needs zero new
# entries for either, since TOPIC_SYMBOLS keys purely by name.

_ACCOUNTING_GRADE11_TOPICS: list[tuple[str, "str | tuple[str, int, str] | None"]] = [
    ("Bank Reconciliation", ("Accounting", 10, "Cash Journals (CRJ, CPJ, PCJ)")),
    ("Creditors' Reconciliation", ("Accounting", 10, "Credit Journals (DJ, DAJ, CJ, CAJ, GJ)")),
    ("Fixed Assets", "Creditors' Reconciliation"),
    ("Partnerships: Concepts and Formation", ("Accounting", 10, "The Accounting Equation")),
    ("Partnership Final Accounts and Year-End Adjustments", "Partnerships: Concepts and Formation"),
    ("Partnership Financial Statements", "Partnership Final Accounts and Year-End Adjustments"),
    ("Analysis and Interpretation of Financial Statements", "Partnership Financial Statements"),
    ("Budgeting (Cash Budget)", ("Accounting", 10, "Budgeting (Cash Budget)")),
    ("Inventory Systems", "Budgeting (Cash Budget)"),
    ("Manufacturing Cost Accounting", "Inventory Systems"),
    ("Value-Added Tax (VAT)", ("Accounting", 10, "Value-Added Tax (VAT)")),
]

_ACCOUNTING_GRADE11_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "Bank Reconciliation": [
        ("A debit order of R450 for insurance appears on the bank statement but "
         "has not yet been entered in the business's Cash Book. State the effect "
         "this has on the Cash Book's bank balance once it is recorded.",
         "The bank balance in the Cash Book decreases by R450"),
        ("Why must items appearing only on the bank statement (such as bank "
         "charges or debit orders) first be recorded in the Cash Book before a "
         "Bank Reconciliation Statement is drawn up?",
         "Because the Cash Book must reflect every transaction that has actually "
         "happened; only once it is updated does its balance represent the true, "
         "correct bank balance to reconcile against the bank statement"),
    ],
    "Creditors' Reconciliation": [
        ("A creditor's statement shows a balance owing of R3 200, but the "
         "Creditors Ledger account for that creditor shows R2 750. Invoice "
         "number 118 for R450 appears on the creditor's statement but has not "
         "yet been recorded in the Creditors Ledger. After recording this "
         "invoice, will the two balances agree?",
         "Yes -- R2 750 + R450 = R3 200, which matches the creditor's statement"),
        ("Name one reason a creditor's statement and the Creditors Ledger might "
         "legitimately differ at month-end, other than an error.",
         "E.g. a payment made by the business near month-end that the creditor "
         "had not yet processed or received (an outstanding payment), or an "
         "invoice/credit note still in transit"),
    ],
    "Fixed Assets": [
        ("A business buys equipment for R20 000 and depreciates it at 10% p.a. "
         "using the straight-line method. Calculate the depreciation for the "
         "first full year.",
         "R2 000 (R20 000 x 10%)"),
        ("A business buys a vehicle for R150 000 and uses the diminishing-"
         "balance method at 20% p.a. Calculate the depreciation for the second "
         "year, given the vehicle's book value at the start of that year is "
         "R120 000.",
         "R24 000 (R120 000 x 20%)"),
    ],
    "Partnerships: Concepts and Formation": [
        ("Name the two accounts kept for each partner in a partnership's books "
         "to record their equity.",
         "The Capital account and the Current account"),
        ("Partner A contributes R80 000 and Partner B contributes R40 000 to "
         "form a partnership, agreeing to share profits equally. State whether "
         "their profit share must be in the same ratio as their capital "
         "contributions.",
         "No -- partners may agree to share profits in any ratio they choose "
         "(e.g. equally), regardless of their capital contribution ratio; this "
         "must be set out in the partnership agreement"),
    ],
    "Partnership Final Accounts and Year-End Adjustments": [
        ("A partnership's Profit and Loss account shows a net profit of "
         "R120 000 for the year, before appropriation. Partner salaries total "
         "R60 000 and interest on capital totals R20 000. Calculate the amount "
         "remaining to be shared between the partners according to their "
         "profit-sharing ratio.",
         "R40 000 (R120 000 - R60 000 - R20 000)"),
        ("At year-end, a partnership has an outstanding electricity account of "
         "R900 that has not yet been paid or recorded. What type of year-end "
         "adjustment does this require?",
         "An accrued expense (expense payable) adjustment -- the R900 must be "
         "added as an expense for the current year even though it hasn't been "
         "paid yet"),
    ],
    "Partnership Financial Statements": [
        ("Which section of a partnership's Statement of Financial Position "
         "shows each partner's Capital and Current account balances?",
         "The Owner's/Partners' Equity section"),
        ("A partnership's Statement of Comprehensive Income is prepared for the "
         "business as a single entity, not split between partners. Which later "
         "section of the accounts DOES split amounts between the individual "
         "partners?",
         "The Appropriation account (the profit distribution/appropriation "
         "section)"),
    ],
    "Analysis and Interpretation of Financial Statements": [
        ("A business has current assets of R90 000 and current liabilities of "
         "R45 000. Calculate the current ratio.",
         "2:1 (90 000 / 45 000)"),
        ("A business's stock turnover rate increases from 6 times per year to "
         "9 times per year. State whether this is generally a favourable or "
         "unfavourable change, and why.",
         "Favourable -- stock is being sold and replaced more often, meaning it "
         "is moving faster and less cash is tied up in unsold stock"),
    ],
    "Budgeting (Cash Budget)": [
        ("A business's Cash Budget projects total cash receipts of R85 000 and "
         "total cash payments of R97 000 for March. Calculate the expected "
         "bank balance at the end of March if the bank balance at the start of "
         "March was R15 000.",
         "R3 000 (15 000 + 85 000 - 97 000)"),
        ("State one key difference between a Cash Budget and a Projected "
         "Income Statement.",
         "A Cash Budget shows only actual cash expected to be received and "
         "paid (e.g. excludes depreciation, includes loan capital repayments), "
         "while a Projected Income Statement shows expected income and "
         "expenses on the accrual basis (e.g. includes depreciation, excludes "
         "loan capital repayments)"),
    ],
    "Inventory Systems": [
        ("Name the two stock systems a business can use to record its "
         "inventory.",
         "The perpetual (continuous) inventory system and the periodic "
         "inventory system"),
        ("Under the perpetual inventory system, which ledger account is "
         "updated immediately every time stock is bought or sold?",
         "The Trading Stock account"),
    ],
    "Manufacturing Cost Accounting": [
        ("A factory's fixed costs for the month are R40 000 and its variable "
         "cost per unit is R25. Calculate the total production cost for 1 000 "
         "units.",
         "R65 000 (R40 000 + (1 000 x R25))"),
        ("Name the three categories of cost that make up the total cost of a "
         "manufactured product.",
         "Direct material cost, direct labour cost, and factory overhead cost"),
    ],
    "Value-Added Tax (VAT)": [
        ("Name one type of item that is zero-rated for VAT purposes in South "
         "Africa.",
         "E.g. basic foodstuffs such as brown bread, maize meal, or milk (any "
         "correct zero-rated item)"),
        ("A debtor's account of R1 150 (VAT-inclusive, at 15%) is written off "
         "as a bad debt. Calculate how much of this amount relates to VAT, "
         "which the business can claim back from SARS.",
         "R150 (1 150 / 1.15 x 0.15, i.e. the VAT portion of the written-off "
         "amount)"),
    ],
}

# --- English Home Language / isiZulu Home Language, Grade 10 (added 14
# Nov 2026, ADR-020) ---
# The first subject with no equation- or ledger-shaped content anywhere in
# it (see ADR-020) -- topic names/structure follow the DBE's own national
# Grade 10 Home Language Annual Teaching Plan, which uses the SAME four
# CAPS skill strands for every official language's Home Language (checked
# 14 Nov 2026): Listening and Speaking, Reading and Viewing, Writing and
# Presenting, and Language Structures and Conventions. Both languages below
# therefore reuse the exact same five topic names -- the same "same name,
# different Subject row" convention Grade 10/11 already use across grades,
# applied here across languages instead, since it's genuinely the same
# skill. Literature topics stay text-agnostic (genre-general, not tied to
# a named novel/poem) since the actual prescribed-text list comes from a
# separate, periodically-revised DBE circular not reliably known here --
# see ADR-020.
#
# *** isiZulu content below has NOT been reviewed by a fluent isiZulu
# speaker. *** Per Siya's own explicit choice (ADR-020): ship it now using
# this project's usual "ship then verify" discipline, but flagged loudly
# because this is unverified CONTENT correctness, not an untested code
# path -- do not treat it as authoritative until reviewed. Examples were
# deliberately kept to simple, well-documented linguistic facts (the
# noun-class system, basic vocabulary) to bound the risk, but simple is
# not the same as verified.

_ENGLISH_HL_TOPICS: list[tuple[str, str | None]] = [
    ("Language Structures and Conventions", None),
    ("Listening and Speaking", "Language Structures and Conventions"),
    ("Reading and Viewing: Literature (Poetry and Drama)", "Listening and Speaking"),
    ("Reading and Viewing: Visual and Media Texts", "Reading and Viewing: Literature (Poetry and Drama)"),
    ("Writing and Presenting", "Reading and Viewing: Visual and Media Texts"),
]

_ENGLISH_HL_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "Language Structures and Conventions": [
        ("Identify the tense used in this sentence and rewrite it in the "
         "past tense: 'She writes a letter every morning.'",
         "Present tense; past tense: 'She wrote a letter every morning.'"),
        ("Name the figure of speech used in the sentence: 'The wind "
         "whispered through the trees.'",
         "Personification -- giving a human quality (whispering) to "
         "something non-human (the wind)"),
    ],
    "Listening and Speaking": [
        ("List two features that distinguish a prepared speech from an "
         "unprepared (impromptu) speech.",
         "E.g. a prepared speech is researched and rehearsed in advance "
         "with a planned structure, while an unprepared speech is "
         "delivered with little or no preparation time, relying on the "
         "speaker's quick thinking"),
        ("Name one non-verbal technique a speaker can use to engage an "
         "audience during a speech.",
         "E.g. eye contact, appropriate gestures, varying tone and pace, "
         "or purposeful pausing"),
    ],
    "Reading and Viewing: Literature (Poetry and Drama)": [
        ("Explain the difference between a simile and a metaphor, giving "
         "one example of each.",
         "A simile compares two things using 'like' or 'as' (e.g. 'brave "
         "as a lion'); a metaphor states that one thing IS another, "
         "without 'like' or 'as' (e.g. 'he is a lion in battle')"),
        ("In a play script, what is the purpose of stage directions?",
         "They instruct actors and the director on movement, tone, and "
         "staging -- guiding how the dialogue should be performed, not "
         "part of the spoken dialogue itself"),
    ],
    "Reading and Viewing: Visual and Media Texts": [
        ("When analysing a print advertisement, name two visual "
         "techniques an advertiser might use to persuade a viewer.",
         "E.g. bold colour contrast to draw the eye, a celebrity or "
         "aspirational image, strategic use of white space, or a slogan "
         "placed prominently"),
        ("What is the purpose of a political cartoon?",
         "To comment critically, often satirically, on a current event, "
         "person, or issue, using exaggeration and symbolism to make a "
         "point quickly and memorably"),
    ],
    "Writing and Presenting": [
        ("Name the three essay types typically examined in Grade 10 Home "
         "Language, and briefly state the purpose of one.",
         "Narrative (tells a story), descriptive (creates a vivid picture "
         "of a person/place/experience), and argumentative (persuades the "
         "reader of a viewpoint) -- e.g. a narrative essay recounts a "
         "sequence of events, often from personal experience, in an "
         "engaging way"),
        ("What is the key difference between a formal letter and an "
         "informal letter in terms of language register?",
         "A formal letter uses respectful, impersonal, grammatically "
         "correct language for an unfamiliar or official reader (e.g. "
         "'Dear Sir/Madam'), while an informal letter uses casual, "
         "personal language for someone you know well (e.g. 'Hi Thabo')"),
    ],
}

_ISIZULU_HL_TOPICS: list[tuple[str, str | None]] = [
    ("Language Structures and Conventions", None),
    ("Listening and Speaking", "Language Structures and Conventions"),
    ("Reading and Viewing: Literature (Poetry and Drama)", "Listening and Speaking"),
    ("Reading and Viewing: Visual and Media Texts", "Reading and Viewing: Literature (Poetry and Drama)"),
    ("Writing and Presenting", "Reading and Viewing: Visual and Media Texts"),
]

_ISIZULU_HL_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "Language Structures and Conventions": [
        ("Identify the noun class of 'umfundi' (student) and give one "
         "other isiZulu noun from the same class.",
         "Class 1 (umu-/aba- class, singular/plural human nouns); "
         "another noun in this class: 'umfana' (boy) -- plural "
         "'abafana'"),
        ("What is the isiZulu word for 'book', and what is its plural "
         "form?",
         "'incwadi' (book); plural: 'izincwadi' (books) -- class 9/10"),
    ],
    "Listening and Speaking": [
        ("Name one traditional isiZulu oral form used for public or "
         "ceremonial speech.",
         "E.g. izibongo (praise poetry) -- a traditional oral form that "
         "praises a person's, clan's, or significant event's lineage and "
         "deeds, traditionally performed aloud rather than read silently"),
        ("List two features that distinguish a prepared speech from an "
         "unprepared (impromptu) speech.",
         "E.g. a prepared speech is researched and rehearsed in advance "
         "with a planned structure, while an unprepared speech is "
         "delivered with little or no preparation time, relying on the "
         "speaker's quick thinking"),
    ],
    "Reading and Viewing: Literature (Poetry and Drama)": [
        ("What are 'izibongo', and what role do they traditionally play "
         "in isiZulu culture?",
         "Praise poems -- a traditional oral poetic form that praises a "
         "person's (often a chief's or ancestor's) lineage, deeds, and "
         "character"),
        ("In a play script (umdlalo), what is the purpose of stage "
         "directions?",
         "They instruct actors and the director on movement, tone, and "
         "staging -- guiding how the dialogue should be performed, not "
         "part of the spoken dialogue itself"),
    ],
    "Reading and Viewing: Visual and Media Texts": [
        ("When analysing a print advertisement, name two visual "
         "techniques an advertiser might use to persuade a viewer.",
         "E.g. bold colour contrast to draw the eye, a celebrity or "
         "aspirational image, strategic use of white space, or a slogan "
         "placed prominently"),
        ("What is the purpose of a political cartoon (ikhathuni "
         "yezombangazwe)?",
         "To comment critically, often satirically, on a current event, "
         "person, or issue, using exaggeration and symbolism to make a "
         "point quickly and memorably"),
    ],
    "Writing and Presenting": [
        ("Name the three essay types typically examined in Grade 10 Home "
         "Language, and briefly state the purpose of one.",
         "Narrative (tells a story), descriptive (creates a vivid picture "
         "of a person/place/experience), and argumentative (persuades the "
         "reader of a viewpoint) -- e.g. a narrative essay recounts a "
         "sequence of events, often from personal experience, in an "
         "engaging way"),
        ("What isiZulu greeting might open an informal letter to someone "
         "you know well, and what is its English equivalent register?",
         "'Sawubona' (hello/greetings to one person) -- an informal "
         "opening, matching the register of an English informal letter "
         "opening such as 'Hi' rather than the formal 'Dear Sir/Madam'"),
    ],
}

# --- Pure Mathematics, Grade 12 (added 15 Nov 2026, ADR-022) ---
# Topic names/order follow the DBE CAPS Grade 12 Mathematics Annual
# Teaching Plan (education.gov.za CAPS FET Mathematics, checked 15 Nov
# 2026): Term 1 (sequences/series, functions, exponential/log, finance,
# trig compound angles), Term 2 (trig 2D/3D, polynomials, differential
# calculus, analytical geometry), Term 3 (Euclidean geometry, stats
# regression/correlation, counting and probability). Linear Programming
# was checked for and confirmed NOT part of the current CAPS Mathematics
# curriculum (removed in an earlier curriculum revision) -- not omitted
# by oversight.
#
# Topics that are a genuine, identical-skill deepening of their exact
# Grade 11 counterpart reuse that exact name (Finance Growth and Decay,
# Analytical Geometry, Euclidean Geometry -- same convention Grade 11
# already used for its own Grade 10 counterparts). Topics where CAPS
# itself introduces materially new sub-skills under a related umbrella
# get a new, more specific name instead (Functions -> "Functions and
# Inverse Functions"; Trigonometry -> "Trigonometry: Compound Angles" --
# the same naming pattern Grade 11's "Exponents and Surds" already set,
# not reusing bare "Exponents"). Three independent chains: a
# Functions/Calculus chain, a Trigonometry chain, and a set of topics
# each anchored directly to their own Grade 11 counterpart.
#
# KNOWN OPEN RISK, flagged before any live test (see ADR-022): Differential
# Calculus introduces notation (f'(x), first-principles limits) that no
# prior Maths/Physical Sciences content has used, and a check of
# math_validator.py found zero existing handling for derivative or limit
# notation -- not confirmed broken, not confirmed working, genuinely
# untested. Consistent with this project's "don't guess a fix before a
# real failure" discipline, no speculative fix is included here.

_MATHS_GRADE12_TOPICS: list[tuple[str, "str | tuple[str, int, str] | None"]] = [
    ("Sequences and Series", ("Pure Mathematics", 11, "Number Patterns")),
    ("Functions and Inverse Functions", ("Pure Mathematics", 11, "Functions")),
    ("Exponential and Logarithmic Functions", "Functions and Inverse Functions"),
    ("Finance, Growth and Decay", ("Pure Mathematics", 11, "Finance, Growth and Decay")),
    ("Trigonometry: Compound Angles", ("Pure Mathematics", 11, "Trigonometry")),
    ("Trigonometry: 2D and 3D Problems", "Trigonometry: Compound Angles"),
    ("Polynomials", "Functions and Inverse Functions"),
    ("Differential Calculus", "Polynomials"),
    ("Analytical Geometry", ("Pure Mathematics", 11, "Analytical Geometry")),
    ("Euclidean Geometry", ("Pure Mathematics", 11, "Euclidean Geometry")),
    ("Statistics: Regression and Correlation", ("Pure Mathematics", 11, "Statistics")),
    ("Counting and Probability", ("Pure Mathematics", 11, "Probability")),
]

_MATHS_GRADE12_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "Sequences and Series": [
        ("Determine the sum of the first 20 terms of the arithmetic series 3 + 7 + 11 + 15 + ...",
         "S20 = 10*(2*3 + 19*4) = 820"),
        ("A geometric series has first term a = 8 and common ratio r = 1/2. Calculate the sum to infinity.",
         "S-infinity = a/(1-r) = 8/0.5 = 16"),
    ],
    "Functions and Inverse Functions": [
        ("Determine the inverse of f(x) = 2x + 3, writing your answer as f^-1(x).",
         "f^-1(x) = (x - 3)/2"),
        ("For f(x) = x^2 (x >= 0), determine f^-1(x) and state its domain.",
         "f^-1(x) = sqrt(x), domain x >= 0"),
    ],
    "Exponential and Logarithmic Functions": [
        ("Write y = 3^x in logarithmic form.", "x = log base 3 of y"),
        ("Solve for x: log base 2 of x = 5", "x = 32"),
    ],
    "Finance, Growth and Decay": [
        ("Calculate the effective annual interest rate if the nominal annual rate is 12% "
         "compounded monthly.", "i_eff = (1 + 0.12/12)^12 - 1 ~= 12.68%"),
        ("Calculate the future value of an ordinary annuity of R1000 paid at the end of each "
         "year for 3 years at 8% p.a. compound interest.",
         "F = 1000*((1.08^3 - 1)/0.08) = R3246.40"),
    ],
    "Trigonometry: Compound Angles": [
        ("Expand sin(A + B) using the compound angle identity.", "sin(A+B) = sinA*cosB + cosA*sinB"),
        ("Simplify cos(60 degrees - 30 degrees) using the compound angle formula and evaluate.",
         "cos60*cos30 + sin60*sin30 = 0.5*(sqrt(3)/2) + (sqrt(3)/2)*0.5 ~= 0.87 (= cos30 degrees)"),
    ],
    "Trigonometry: 2D and 3D Problems": [
        ("In triangle ABC, AB = 10 cm, angle A = 40 degrees, angle B = 60 degrees. Use the "
         "sine rule to calculate BC.",
         "angle C = 80 degrees; BC = 10*sin(40)/sin(80) ~= 6.53 cm"),
        ("State the Area Rule for a triangle in terms of two sides and the included angle.",
         "Area = (1/2)*a*b*sin(C)"),
    ],
    "Polynomials": [
        ("Use the Factor Theorem to show that (x - 1) is a factor of f(x) = x^3 - 6x^2 + 11x - 6.",
         "f(1) = 1 - 6 + 11 - 6 = 0, so (x-1) is a factor"),
        ("Factorise fully: x^3 - 6x^2 + 11x - 6, given that (x - 1) is a factor.",
         "(x-1)(x-2)(x-3)"),
    ],
    "Differential Calculus": [
        ("Determine f'(x) from first principles for f(x) = x^2.",
         "f'(x) = lim(h->0) [(x+h)^2 - x^2]/h = lim(h->0) (2xh+h^2)/h = 2x"),
        ("Determine the derivative of f(x) = 3x^2 - 4x + 5 using the rules of differentiation.",
         "f'(x) = 6x - 4"),
    ],
    "Analytical Geometry": [
        ("Determine the equation of a circle with centre (2, -1) and radius 5.",
         "(x-2)^2 + (y+1)^2 = 25"),
        ("A circle has equation x^2 + y^2 = 25. Determine the gradient of the tangent to the "
         "circle at the point (3,4).",
         "gradient of radius = 4/3; tangent gradient = -3/4 (perpendicular to the radius)"),
    ],
    "Euclidean Geometry": [
        ("State the Proportionality Theorem for a line drawn parallel to one side of a triangle.",
         "A line drawn parallel to one side of a triangle divides the other two sides proportionally"),
        ("Triangle ABC is similar to triangle DEF. If AB = 6 cm, DE = 9 cm, and BC = 8 cm, "
         "calculate EF.",
         "EF = BC * (DE/AB) = 8 * (9/6) = 12 cm"),
    ],
    "Statistics: Regression and Correlation": [
        ("State what a correlation coefficient of r = -0.9 indicates about the relationship "
         "between two variables.",
         "A strong negative linear relationship: as one variable increases, the other tends "
         "to decrease"),
        ("Given a least-squares regression line y-hat = 2 + 3x, estimate y when x = 5.",
         "y-hat = 2 + 3*5 = 17"),
    ],
    "Counting and Probability": [
        ("In how many ways can 5 different books be arranged on a shelf?", "5! = 120"),
        ("From a group of 8 people, how many different committees of 3 people can be chosen "
         "(order doesn't matter)?", "C(8,3) = 56"),
    ],
}

# --- Physical Sciences, Grade 12 -- Physics strand only (added 15 Nov
# 2026, ADR-022), same strand-only scoping as Grade 10/11 (see ADR-013)
# ---
# Topic content follows the DBE CAPS Grade 12 Physical Sciences document
# (education.gov.za CAPS FET Physical Science, checked 15 Nov 2026): a
# Mechanics chain (Momentum and Impulse -> Vertical Projectile Motion ->
# Work, Energy and Power, matching CAPS' own Term 1 teaching order),
# Doppler Effect (Waves/Sound/Light strand -- no Grade 11 Waves topic
# exists in this project at all, so this anchors directly to Grade 10's
# "Waves, Sound and Light", skipping Grade 11 the same way a cross-grade
# reference is allowed to), Electric Circuits (reused name -- Grade 12
# adds internal resistance and series-parallel networks to the Grade 11
# skill), Electrodynamics (generators/motors/AC, the natural continuation
# of Grade 11 Electromagnetism), and Photoelectric Effect (anchored to
# Grade 10's Electromagnetic Radiation, since CAPS' EM-spectrum/photon-
# energy basics are Grade 10 content and only the photoelectric effect
# itself is new at Grade 12).

_PHYSICAL_SCIENCES_GRADE12_TOPICS: list[tuple[str, "str | tuple[str, int, str] | None"]] = [
    ("Momentum and Impulse", ("Physical Sciences", 11, "Newton's Laws")),
    ("Vertical Projectile Motion", "Momentum and Impulse"),
    ("Work, Energy and Power", "Vertical Projectile Motion"),
    ("Doppler Effect", ("Physical Sciences", 10, "Waves, Sound and Light")),
    ("Electric Circuits", ("Physical Sciences", 11, "Electric Circuits")),
    ("Electrodynamics", ("Physical Sciences", 11, "Electromagnetism")),
    ("Photoelectric Effect", ("Physical Sciences", 10, "Electromagnetic Radiation")),
]

_PHYSICAL_SCIENCES_GRADE12_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "Momentum and Impulse": [
        ("Calculate the momentum of a 2 kg object moving at 5 m/s.", "p = mv = 10 kg.m/s"),
        ("A 0.5 kg ball travelling at 4 m/s is brought to rest in 0.2 s. Calculate the "
         "average force exerted on it.",
         "F = delta-p / delta-t = (0 - 0.5*4)/0.2 = -10 N (10 N, opposite to the motion)"),
    ],
    "Vertical Projectile Motion": [
        ("A ball is thrown vertically upward at 20 m/s. Calculate the maximum height "
         "reached (take g = 10 m/s^2, ignore air resistance).",
         "v^2 = u^2 - 2gh; 0 = 400 - 20h; h = 20 m"),
        ("A stone is dropped from a height of 45 m. Calculate the time it takes to reach "
         "the ground (g = 10 m/s^2).",
         "h = (1/2)g*t^2; 45 = 5t^2; t = 3 s"),
    ],
    "Work, Energy and Power": [
        ("Calculate the work done by a 50 N force moving an object 4 m in the direction "
         "of the force.", "W = F * delta-x = 200 J"),
        ("A motor lifts a 20 kg mass through a height of 3 m in 2 s. Calculate the power "
         "delivered (g = 10 m/s^2).",
         "P = W/t = (mgh)/t = (20*10*3)/2 = 300 W"),
    ],
    "Doppler Effect": [
        ("State what happens to the observed frequency of a sound as its source moves "
         "towards a stationary listener.",
         "The observed frequency increases (the sound is heard at a higher pitch)"),
        ("A car's hooter emits a frequency of 500 Hz while moving towards a stationary "
         "listener at 20 m/s (speed of sound = 340 m/s). Calculate the frequency heard "
         "by the listener.",
         "fL = fs * v/(v - vs) = 500 * 340/320 ~= 531.25 Hz"),
    ],
    "Electric Circuits": [
        ("A battery has an EMF of 12 V and internal resistance 0.5 ohm. When it delivers "
         "a current of 3 A, calculate the terminal potential difference.",
         "V = EMF - Ir = 12 - 1.5 = 10.5 V"),
        ("Calculate the equivalent resistance of a network with a 4 ohm resistor in "
         "series with a parallel combination of two 6 ohm resistors.",
         "Parallel pair = 3 ohm; total = 4 + 3 = 7 ohm"),
    ],
    "Electrodynamics": [
        ("State the energy conversion that takes place in an electric generator.",
         "Kinetic (mechanical) energy is converted into electrical energy"),
        ("State one difference between an AC generator and a DC generator.",
         "An AC generator uses slip rings (producing alternating current that reverses "
         "direction), while a DC generator uses a split-ring commutator (producing "
         "current in one direction only)"),
    ],
    "Photoelectric Effect": [
        ("Calculate the energy of a photon with frequency 6x10^14 Hz (h = 6.63x10^-34 J.s).",
         "E = hf = 6.63x10^-34 * 6x10^14 ~= 3.98x10^-19 J"),
        ("State what is meant by the 'work function' of a metal in the context of the "
         "photoelectric effect.",
         "The minimum energy needed to emit an electron from the surface of a metal"),
    ],
}

# --- Accounting, Grade 12 (added 15 Nov 2026, ADR-022) ---
# Topic content follows the DBE CAPS Grade 12 Accounting Annual Teaching
# Plan (education.gov.za, checked 15 Nov 2026): a Companies chain
# (Concepts and Ledger Accounts -> Final Accounts and Year-End
# Adjustments -> Financial Statements -> Cash Flow Statement -> Analysis
# and Interpretation of Financial Statements, matching CAPS' own Term 1
# order -- the same "new business entity gets its own linear trunk"
# shape ADR-019 used for Partnerships at Grade 11), five topics that are
# a genuine deepening of their exact Grade 11 counterpart and reuse that
# exact name (Fixed Assets, Inventory Systems, Value-Added Tax (VAT),
# Manufacturing Cost Accounting, Budgeting (Cash Budget) -- same
# convention ADR-019 itself used for Budgeting/VAT), one topic merging
# CAPS' three separate Grade 12 reconciliation types (bank, debtors,
# creditors) into a single unit anchored to Grade 11's Bank
# Reconciliation, and Close Corporations as a standalone new-entity
# topic with no cross-grade anchor -- deliberately, the same "no clean
# counterpart" judgment call ADR-019 made for Fixed Assets at Grade 11.
#
# Verification stance unchanged from ADR-018/ADR-019: still no
# MathGuard-style checking.

_ACCOUNTING_GRADE12_TOPICS: list[tuple[str, "str | tuple[str, int, str] | None"]] = [
    ("Companies: Concepts and Ledger Accounts", ("Accounting", 11, "Partnerships: Concepts and Formation")),
    ("Companies: Final Accounts and Year-End Adjustments", "Companies: Concepts and Ledger Accounts"),
    ("Companies: Financial Statements", "Companies: Final Accounts and Year-End Adjustments"),
    ("Cash Flow Statement", "Companies: Financial Statements"),
    ("Analysis and Interpretation of Financial Statements", "Cash Flow Statement"),
    ("Fixed Assets", ("Accounting", 11, "Fixed Assets")),
    ("Inventory Systems", ("Accounting", 11, "Inventory Systems")),
    ("Reconciliations (Bank, Debtors and Creditors)", ("Accounting", 11, "Bank Reconciliation")),
    ("Value-Added Tax (VAT)", ("Accounting", 11, "Value-Added Tax (VAT)")),
    ("Manufacturing Cost Accounting", ("Accounting", 11, "Manufacturing Cost Accounting")),
    ("Budgeting (Cash Budget)", ("Accounting", 11, "Budgeting (Cash Budget)")),
    ("Close Corporations", None),
]

_ACCOUNTING_GRADE12_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "Companies: Concepts and Ledger Accounts": [
        ("Name the two types of companies recognised under the Companies Act that Grade "
         "12 Accounting covers.", "Public companies (Ltd) and private companies (Pty Ltd)"),
        ("A company issues 10 000 ordinary shares at R5 each. Calculate the total amount "
         "received from this share issue.", "R50 000 (10 000 x R5)"),
    ],
    "Companies: Final Accounts and Year-End Adjustments": [
        ("A company's net profit before tax is R400 000. Calculate the company's income "
         "tax payable at a rate of 28%.", "R112 000 (R400 000 x 28%)"),
        ("A company declares a final dividend of 50 cents per share on 20 000 shares. "
         "Calculate the total dividends declared.", "R10 000 (20 000 x R0.50)"),
    ],
    "Companies: Financial Statements": [
        ("Name the three main financial statements a company prepares at year-end.",
         "The Income Statement, the Balance Sheet (Statement of Financial Position), "
         "and the Cash Flow Statement"),
        ("Which section of a company's Balance Sheet shows retained earnings and share "
         "capital?", "The Shareholders' Equity section"),
    ],
    "Cash Flow Statement": [
        ("Name the three main sections of a Cash Flow Statement.",
         "Cash flow from operating activities, cash flow from investing activities, and "
         "cash flow from financing activities"),
        ("A company repays a long-term loan of R50 000 during the year. Under which "
         "section of the Cash Flow Statement does this appear?",
         "Cash flow from financing activities (as a cash outflow)"),
    ],
    "Analysis and Interpretation of Financial Statements": [
        ("A company has 20 000 shares in issue and a net profit after tax of R300 000. "
         "Calculate the earnings per share (EPS).", "EPS = R300 000 / 20 000 = R15 per share"),
        ("State the purpose of an independent auditor's report attached to a company's "
         "published financial statements.",
         "To give shareholders and other users an independent opinion on whether the "
         "financial statements fairly present the company's financial position"),
    ],
    "Fixed Assets": [
        ("Explain what is meant by the 'average age' of a fixed asset and why it matters "
         "to a company's decision-makers.",
         "It indicates roughly how old/worn an asset is relative to its useful life, "
         "helping decide whether it needs to be replaced soon"),
        ("A company's land and buildings have not been revalued in 10 years despite "
         "rising property prices. State one effect this has on the Balance Sheet.",
         "The Balance Sheet understates the true (market) value of the land and "
         "buildings, since they are shown at historical cost less depreciation"),
    ],
    "Inventory Systems": [
        ("Under the FIFO method, which units of stock are assumed to be sold first?",
         "The units purchased first (First-In, First-Out)"),
        ("A business buys 100 units at R10 each, then 100 units at R12 each, and sells "
         "120 units. Using FIFO, calculate the cost of the 120 units sold.",
         "100 x R10 + 20 x R12 = R1 000 + R240 = R1 240"),
    ],
    "Reconciliations (Bank, Debtors and Creditors)": [
        ("A debtor's age analysis shows R2 000 of a debtor's balance is more than 90 "
         "days overdue. State one reason a business might increase its provision for "
         "bad debts based on this.",
         "The longer a debt remains unpaid, the less likely it is to ever be collected, "
         "so the risk of it becoming a bad debt increases"),
        ("Explain the purpose of a debtors' reconciliation.",
         "To compare the balance on a debtor's account in the Debtors Ledger with the "
         "debtor's own statement, and identify and correct any differences"),
    ],
    "Value-Added Tax (VAT)": [
        ("A business's VAT Control account shows VAT Output of R45 000 and VAT Input of "
         "R30 000 for the period. Calculate the amount payable to SARS.",
         "R15 000 (R45 000 - R30 000)"),
        ("If VAT Input exceeds VAT Output for a period, what does this mean for the "
         "business?", "SARS owes the business a VAT refund, rather than the business "
         "owing SARS"),
    ],
    "Manufacturing Cost Accounting": [
        ("A factory produces 2 000 units at a total production cost of R180 000. "
         "Calculate the unit cost of production.", "R90 per unit (R180 000 / 2 000)"),
        ("A product sells for R150 and has a variable cost of R90 per unit, with total "
         "fixed costs of R36 000 per month. Calculate the break-even number of units.",
         "Break-even = fixed costs / (selling price - variable cost) = 36 000 / 60 = "
         "600 units"),
    ],
    "Budgeting (Cash Budget)": [
        ("A business's actual cash sales for March were R80 000 against a budgeted "
         "R95 000. Calculate the variance and state whether it is favourable or "
         "unfavourable.", "R15 000 unfavourable (actual sales were R15 000 less than "
         "budgeted)"),
        ("Name one reason a business might compare its Cash Budget figures to actual "
         "results each month.",
         "To identify and investigate significant differences (variances) early, so "
         "corrective action can be taken"),
    ],
    "Close Corporations": [
        ("What does the abbreviation 'CC' after a business name indicate?",
         "That the business is registered as a Close Corporation"),
        ("State one key difference between a Close Corporation and a company regarding "
         "ownership.",
         "A Close Corporation has members (not shareholders), with a maximum of 10 "
         "members, and no share capital"),
    ],
}

# --- English Home Language, Grade 11 and Grade 12 (added 15 Nov 2026,
# ADR-023) ---
# Siya's explicit choice (15 Nov 2026): pause isiZulu Home Language work
# (its real-content-accuracy fix, ADR-021's RAG ingestion pipeline, is
# still in progress and deliberately not touched here) and proceed with
# the rest of the grade scale-up, which includes English Home Language.
# Reuses the exact same 5-topic template ADR-020 established at Grade 10
# -- confirmed again by checking the DBE's own CAPS Home Language
# document (checked 15 Nov 2026): the same four skill strands apply at
# every FET grade, with complexity (comprehension passage length, poem
# count, essay length) increasing per grade rather than the strand
# structure changing. Each grade's root topic (Language Structures and
# Conventions) cross-grade-anchors to the previous grade's version, the
# same escalating-chain shape every other subject already uses across
# its own grades; the other four topics chain within-grade exactly as
# Grade 10 did. isiZulu Home Language Grade 11/12 do NOT exist -- not an
# oversight, see ADR-023.

_ENGLISH_HL_GRADE11_TOPICS: list[tuple[str, "str | tuple[str, int, str] | None"]] = [
    ("Language Structures and Conventions", ("English Home Language", 10, "Language Structures and Conventions")),
    ("Listening and Speaking", "Language Structures and Conventions"),
    ("Reading and Viewing: Literature (Poetry and Drama)", "Listening and Speaking"),
    ("Reading and Viewing: Visual and Media Texts", "Reading and Viewing: Literature (Poetry and Drama)"),
    ("Writing and Presenting", "Reading and Viewing: Visual and Media Texts"),
]

_ENGLISH_HL_GRADE11_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "Language Structures and Conventions": [
        ("Identify the figure of speech in: 'Time is a thief that steals our youth.'",
         "Metaphor (time is described as a thief, without using 'like' or 'as')"),
        ("Rewrite in the passive voice: 'The committee approved the proposal.'",
         "The proposal was approved by the committee"),
    ],
    "Listening and Speaking": [
        ("Name one feature that distinguishes a formal debate speech from an informal "
         "conversation.",
         "A formal debate speech follows a structured argument with evidence and "
         "rebuttal, uses formal register, and observes time limits and turn-taking "
         "rules, unlike casual conversation"),
        ("State the purpose of using visual aids (e.g. slides) during an oral "
         "presentation.",
         "To support and clarify the spoken content, making complex information "
         "easier for the audience to follow and remember"),
    ],
    "Reading and Viewing: Literature (Poetry and Drama)": [
        ("Identify the figure of speech in the line 'The silence screamed at him.'",
         "Oxymoron (silence, by definition soundless, is described as screaming)"),
        ("Explain the dramatic purpose of a soliloquy in a play.",
         "It allows a character to reveal their private thoughts and feelings "
         "directly to the audience, when no other character is present to hear them"),
    ],
    "Reading and Viewing: Visual and Media Texts": [
        ("Explain how camera angle can influence a viewer's perception of a character "
         "in a film (e.g. a low-angle shot).",
         "A low-angle shot, looking up at a character, tends to make them appear "
         "powerful or dominant, while a high-angle shot looking down can make them "
         "appear weak or vulnerable"),
        ("State the purpose of a caption accompanying a news photograph.",
         "To provide context that explains what the image shows, since a photograph "
         "alone can be ambiguous or open to misinterpretation"),
    ],
    "Writing and Presenting": [
        ("Name the three main sections a formal discursive essay should have.",
         "An introduction (stating the topic and viewpoint), a body (arguments and "
         "counter-arguments with evidence), and a conclusion (summarising the "
         "position)"),
        ("State the main difference in register between a formal letter of complaint "
         "and a friendly email.",
         "A formal letter of complaint uses formal, respectful, objective language "
         "and a structured format, while a friendly email uses casual, personal "
         "language appropriate to someone the writer knows well"),
    ],
}

_ENGLISH_HL_GRADE12_TOPICS: list[tuple[str, "str | tuple[str, int, str] | None"]] = [
    ("Language Structures and Conventions", ("English Home Language", 11, "Language Structures and Conventions")),
    ("Listening and Speaking", "Language Structures and Conventions"),
    ("Reading and Viewing: Literature (Poetry and Drama)", "Listening and Speaking"),
    ("Reading and Viewing: Visual and Media Texts", "Reading and Viewing: Literature (Poetry and Drama)"),
    ("Writing and Presenting", "Reading and Viewing: Visual and Media Texts"),
]

_ENGLISH_HL_GRADE12_QUESTIONS: dict[str, list[tuple[str, str]]] = {
    "Language Structures and Conventions": [
        ("Identify the literary device in: 'It was the best of times, it was the worst "
         "of times.'",
         "Paradox (and antithesis) -- two contrasting ideas placed together to reveal "
         "a deeper truth"),
        ("Explain the effect of using the subjunctive mood in: 'If I were president, I "
         "would change this law.'",
         "It signals a hypothetical, unreal, or wished-for situation -- the speaker "
         "is not actually president"),
    ],
    "Listening and Speaking": [
        ("Explain the difference between persuasive and propagandistic rhetoric in a "
         "public speech.",
         "Persuasive rhetoric uses sound reasoning and evidence to convince an "
         "audience, while propaganda relies on emotional manipulation, selective "
         "facts, or misinformation to control opinion"),
        ("State why pacing and pause are important rhetorical tools in a formal speech.",
         "They give the audience time to absorb key points and create emphasis, "
         "preventing the delivery from sounding rushed or monotonous"),
    ],
    "Reading and Viewing: Literature (Poetry and Drama)": [
        ("Explain the function of dramatic irony in a tragedy, where the audience "
         "knows something a character does not.",
         "It creates tension and emotional engagement, since the audience "
         "anticipates the consequences of the character's ignorance before the "
         "character does"),
        ("Identify and explain the effect of enjambment in a poem where a sentence "
         "runs on without pause from one line to the next.",
         "Enjambment creates a sense of flow, urgency, or continuation of thought, "
         "forcing the reader onward to the next line to complete the sense"),
    ],
    "Reading and Viewing: Visual and Media Texts": [
        ("Explain how juxtaposition of two contrasting images in a political cartoon "
         "can create satire.",
         "Placing two contrasting images or ideas side by side highlights the "
         "contradiction or hypocrisy being criticised, prompting the viewer to draw "
         "a critical conclusion"),
        ("State one technique advertisers use to create a false sense of urgency, and "
         "explain its persuasive effect.",
         "E.g. 'limited time offer' or a countdown timer -- it pressures the viewer "
         "to act quickly without fully considering the decision, out of fear of "
         "missing out"),
    ],
    "Writing and Presenting": [
        ("Name the key structural difference between an argumentative essay and a "
         "discursive essay.",
         "An argumentative essay takes and defends one clear side of an issue, while "
         "a discursive essay presents multiple viewpoints in a balanced way without "
         "necessarily taking a firm side"),
        ("State the purpose of a rhetorical question in a persuasive essay's "
         "conclusion.",
         "To prompt the reader to reflect on the argument and arrive at the writer's "
         "intended conclusion themselves, reinforcing the essay's point without "
         "stating it directly again"),
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
        "name": "Accounting",
        "grade": 10,
        "topics": _ACCOUNTING_TOPICS,
        "questions": _ACCOUNTING_QUESTIONS,
    },
    {
        "name": "Accounting",
        "grade": 11,
        "topics": _ACCOUNTING_GRADE11_TOPICS,
        "questions": _ACCOUNTING_GRADE11_QUESTIONS,
    },
    {
        "name": "English Home Language",
        "grade": 10,
        "topics": _ENGLISH_HL_TOPICS,
        "questions": _ENGLISH_HL_QUESTIONS,
    },
    {
        "name": "isiZulu Home Language",
        "grade": 10,
        "topics": _ISIZULU_HL_TOPICS,
        "questions": _ISIZULU_HL_QUESTIONS,
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
    {
        "name": "Pure Mathematics",
        "grade": 12,
        "topics": _MATHS_GRADE12_TOPICS,
        "questions": _MATHS_GRADE12_QUESTIONS,
    },
    {
        "name": "Physical Sciences",
        "grade": 12,
        "topics": _PHYSICAL_SCIENCES_GRADE12_TOPICS,
        "questions": _PHYSICAL_SCIENCES_GRADE12_QUESTIONS,
    },
    {
        "name": "Accounting",
        "grade": 12,
        "topics": _ACCOUNTING_GRADE12_TOPICS,
        "questions": _ACCOUNTING_GRADE12_QUESTIONS,
    },
    {
        "name": "English Home Language",
        "grade": 11,
        "topics": _ENGLISH_HL_GRADE11_TOPICS,
        "questions": _ENGLISH_HL_GRADE11_QUESTIONS,
    },
    {
        "name": "English Home Language",
        "grade": 12,
        "topics": _ENGLISH_HL_GRADE12_TOPICS,
        "questions": _ENGLISH_HL_GRADE12_QUESTIONS,
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


async def get_or_create_topic(
    session, name: str, subject_id, prerequisite_id, order_index: int
) -> Topic:
    """FIX 15 Nov 2026 (live-test finding, order_index column): order_index
    is this topic's position in its subject's own topic list below, which
    follows the real DBE ATP term order (see each subject-addition ADR).
    Unlike every other field here, order_index is refreshed on an EXISTING
    row too, not just set once at creation -- every topic added before
    this fix shipped has whatever default the migration gave it (0), and
    only a re-run of this script actually backfills the real order for
    topics that already existed."""
    result = await session.execute(
        select(Topic).where(Topic.subject_id == subject_id, Topic.name == name)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        if existing.order_index != order_index:
            existing.order_index = order_index
            await session.flush()
        return existing
    topic = Topic(
        subject_id=subject_id,
        name=name,
        prerequisite_id=prerequisite_id,
        order_index=order_index,
    )
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
        # FIX 15 Nov 2026 (ADR-026 follow-up): previously returned the
        # existing row untouched -- same class of bug the order_index
        # fix already caught once this run. Without this, bumping
        # DEV_LEARNER_GRADE above would do nothing for anyone who had
        # already seeded a dev learner before this change landed; a
        # plain re-seed now actually widens (or narrows) what the dev
        # account can see.
        changed = False
        if existing.grade != DEV_LEARNER_GRADE:
            existing.grade = DEV_LEARNER_GRADE
            changed = True
        # FIX 15 Nov 2026 (ADR-027, dev/admin diagnosis bypass). Same
        # "refresh an existing row" fix, third time this applies to this
        # script -- without it, this flag would never actually turn on
        # for anyone who had already seeded a dev learner before ADR-027
        # landed. ONLY this one account gets True; every real student
        # provisioned via the teacher dashboard keeps the model's
        # default of False, so the real diagnosis redirect (ADR-007)
        # stays intact for them.
        if existing.skip_diagnosis is not True:
            existing.skip_diagnosis = True
            changed = True
        if changed:
            await session.flush()
        return existing
    learner = Learner(
        display_name=DEV_LEARNER_NAME,
        grade=DEV_LEARNER_GRADE,
        preferred_modality="balanced",
        # ADR-027: this account has no real attempt history on anything,
        # so it should never be redirected down to a foundational
        # prerequisite -- see tutor_orchestration.py's prepare_tutor_turn().
        skip_diagnosis=True,
    )
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
        # FIX 15 Nov 2026 (found live-testing ADR-024's teacher account,
        # see the matching fix below): refresh the password hash on an
        # existing row too, not just at first creation -- the same
        # "existing row never gets refreshed on re-seed" bug already
        # caught three times this session (order_index, DEV_LEARNER_GRADE,
        # skip_diagnosis), just never applied here since DEV_STUDENT_PASSWORD
        # itself has never changed value -- so the gap was latent, not yet
        # observed, until DEV_TEACHER_PASSWORD's own change exposed the
        # same bug class for the teacher account below.
        existing_user = await session.get(User, learner.user_id)
        existing_user.password_hash = hash_password(DEV_STUDENT_PASSWORD)
        return existing_user

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


async def get_or_create_demo_teacher_account(session, school: School) -> User:
    """
    NEW 15 Nov 2026 (ADR-024, teacher dashboard access + bulk student
    provisioning). Mirrors get_or_create_demo_student_account() above --
    idempotent, so re-running this script doesn't try to provision a
    second teacher with the same staff number and collide. Unlike the
    student account, there's no existing_learner to attach to (a
    teacher has no Learner at all).
    """
    result = await session.execute(
        select(User).where(User.school_id == school.id, User.student_number == DEV_TEACHER_NUMBER)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        # FIX 15 Nov 2026: refresh the password hash on every re-seed --
        # without this, an already-seeded dev teacher row stays hashed
        # against whatever DEV_TEACHER_PASSWORD was AT FIRST CREATION
        # forever. This is exactly what happened: the teacher account was
        # first created back when DEV_TEACHER_PASSWORD was its own separate
        # value ("DevTeachPass123!"), and commit 31ba360 later unified it
        # with DEV_STUDENT_PASSWORD -- but every re-seed since then kept
        # returning this row untouched, so the login screen's documented
        # DevPass123! never actually matched the stored hash. Confirmed via
        # a direct DB check during live-testing (verify_password returned
        # False against the documented password on an existing row).
        existing.password_hash = hash_password(DEV_TEACHER_PASSWORD)
        return existing

    user, _ = await provision_teacher(
        session,
        school=school,
        staff_number=DEV_TEACHER_NUMBER,
        raw_password=DEV_TEACHER_PASSWORD,
    )
    return user


DEV_OFFICIAL_NUMBER = "O00001"          # district official (Demo District Office)
DEV_CIRCUIT_OFFICIAL_NUMBER = "C00001"  # circuit manager (Demo Circuit Office)
DEV_PARENT_NUMBER = "G00001"            # parent of the dev learner 100001 (Demo School)


async def ensure_dev_insights(session, school: School) -> None:
    """
    NEW 19 Nov 2026 (ADR-039). A demo district with one circuit holding the
    demo school, a "Demo Circuit Office" to log in through, and a
    district-level official O00001 (password DevPass123!). Idempotent.
    """
    district = (await session.execute(select(District).where(District.name == "Demo District"))).scalar_one_or_none()
    if district is None:
        district = District(name="Demo District", province="KwaZulu-Natal")
        session.add(district)
        await session.flush()
    circuit = (
        await session.execute(select(Circuit).where(Circuit.name == "Demo Circuit", Circuit.district_id == district.id))
    ).scalar_one_or_none()
    if circuit is None:
        circuit = Circuit(district_id=district.id, name="Demo Circuit")
        session.add(circuit)
        await session.flush()
    school.circuit_id = circuit.id
    office = (
        await session.execute(select(School).where(School.name == "Demo District Office", School.kind == "office"))
    ).scalar_one_or_none()
    if office is None:
        office = School(name="Demo District Office", kind="office")
        session.add(office)
        await session.flush()
    official = (
        await session.execute(
            select(User).where(User.school_id == office.id, User.student_number == DEV_OFFICIAL_NUMBER)
        )
    ).scalar_one_or_none()
    if official is None:
        official = User(role="official", school_id=office.id, student_number=DEV_OFFICIAL_NUMBER)
        session.add(official)
    official.display_name = "Dev Official"
    official.password_hash = hash_password(DEV_STUDENT_PASSWORD)
    official.must_change_password = False
    official.is_active = True
    await session.flush()
    exists = (
        await session.execute(
            select(OfficialAssignment).where(
                OfficialAssignment.user_id == official.id, OfficialAssignment.district_id == district.id
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(OfficialAssignment(user_id=official.id, district_id=district.id))

    # NEW 19 Nov 2026: a circuit manager, logging in through the circuit's office.
    circuit_office = (
        await session.execute(select(School).where(School.name == "Demo Circuit Office", School.kind == "office"))
    ).scalar_one_or_none()
    if circuit_office is None:
        circuit_office = School(name="Demo Circuit Office", kind="office")
        session.add(circuit_office)
        await session.flush()
    manager = (
        await session.execute(
            select(User).where(
                User.school_id == circuit_office.id, User.student_number == DEV_CIRCUIT_OFFICIAL_NUMBER
            )
        )
    ).scalar_one_or_none()
    if manager is None:
        manager = User(role="official", school_id=circuit_office.id, student_number=DEV_CIRCUIT_OFFICIAL_NUMBER)
        session.add(manager)
    manager.display_name = "Dev Circuit Manager"
    manager.password_hash = hash_password(DEV_STUDENT_PASSWORD)
    manager.must_change_password = False
    manager.is_active = True
    await session.flush()
    has_circuit = (
        await session.execute(
            select(OfficialAssignment).where(
                OfficialAssignment.user_id == manager.id, OfficialAssignment.circuit_id == circuit.id
            )
        )
    ).scalar_one_or_none()
    if has_circuit is None:
        session.add(OfficialAssignment(user_id=manager.id, circuit_id=circuit.id))


async def ensure_dev_parent(session, school: School, learner: Learner) -> None:
    """
    NEW 19 Nov 2026 (ADR-038). A parent login G00001 (password DevPass123!)
    linked to the dev learner 100001, for trying the CONNECT view. Idempotent.
    """
    parent = (
        await session.execute(
            select(User).where(User.school_id == school.id, User.student_number == DEV_PARENT_NUMBER)
        )
    ).scalar_one_or_none()
    if parent is None:
        parent = User(role="parent", school_id=school.id, student_number=DEV_PARENT_NUMBER)
        session.add(parent)
    parent.display_name = "Dev Parent"
    parent.password_hash = hash_password(DEV_STUDENT_PASSWORD)
    parent.must_change_password = False
    parent.is_active = True
    await session.flush()
    link = (
        await session.execute(
            select(ParentLink).where(ParentLink.parent_user_id == parent.id, ParentLink.learner_id == learner.id)
        )
    ).scalar_one_or_none()
    if link is None:
        session.add(ParentLink(parent_user_id=parent.id, learner_id=learner.id, relationship_to_learner="Parent"))


async def ensure_dev_school_structure(session, school: School, teacher: User, learner: Learner) -> User:
    """
    NEW 17 Nov 2026 (ADR-031). Idempotent, and refreshes existing rows on
    re-seed (the lesson from the four get_or_create bugs on 15 Nov):
    names, the principal's password and role, class 12A, its membership,
    and T00001's allocation are all (re)asserted every run.
    """
    teacher.display_name = "Dev Teacher"

    principal = (
        await session.execute(
            select(User).where(User.school_id == school.id, User.student_number == DEV_PRINCIPAL_NUMBER)
        )
    ).scalar_one_or_none()
    if principal is None:
        principal, _ = await provision_teacher(
            session, school=school, staff_number=DEV_PRINCIPAL_NUMBER, raw_password=DEV_TEACHER_PASSWORD
        )
    else:
        principal.password_hash = hash_password(DEV_TEACHER_PASSWORD)
    principal.display_name = "Dev Principal"
    has_role = (
        await session.execute(
            select(StaffRole.id).where(StaffRole.user_id == principal.id, StaffRole.role == "principal")
        )
    ).first()
    if not has_role:
        session.add(StaffRole(user_id=principal.id, school_id=school.id, role="principal"))

    cls = (
        await session.execute(
            select(SchoolClass).where(SchoolClass.school_id == school.id, SchoolClass.name == DEV_CLASS_NAME)
        )
    ).scalar_one_or_none()
    if cls is None:
        cls = SchoolClass(school_id=school.id, name=DEV_CLASS_NAME, grade=learner.grade)
        session.add(cls)
        await session.flush()
    cls.grade = learner.grade
    in_class = (
        await session.execute(
            select(ClassMember.id).where(ClassMember.class_id == cls.id, ClassMember.learner_id == learner.id)
        )
    ).first()
    if not in_class:
        session.add(ClassMember(class_id=cls.id, learner_id=learner.id))

    subj_name, subj_grade = DEV_ALLOCATION_SUBJECT
    subject = (
        await session.execute(select(Subject).where(Subject.name == subj_name, Subject.grade == subj_grade))
    ).scalar_one()
    has_alloc = (
        await session.execute(
            select(TeachingAllocation.id).where(
                TeachingAllocation.teacher_user_id == teacher.id,
                TeachingAllocation.subject_id == subject.id,
                TeachingAllocation.class_id == cls.id,
            )
        )
    ).first()
    if not has_alloc:
        session.add(
            TeachingAllocation(
                school_id=school.id, teacher_user_id=teacher.id, subject_id=subject.id, class_id=cls.id
            )
        )
    return principal


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
    for order_index, (name, prereq) in enumerate(subject_spec["topics"]):
        if isinstance(prereq, tuple):
            ref_subject, ref_grade, ref_topic = prereq
            prerequisite_id = all_seeded_topics[(ref_subject, ref_grade)][ref_topic].id
        else:
            prerequisite_id = topics_by_name[prereq].id if prereq else None
        topics_by_name[name] = await get_or_create_topic(
            session, name, subject.id, prerequisite_id, order_index
        )

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

        # NEW 17 Nov 2026 (code review #5): curriculum content (subjects,
        # topics, questions) is needed everywhere, but the demo school and
        # its known-password accounts (DevPass123!) must never exist outside
        # development. Anywhere else this run stops after the content.
        if settings.environment.lower() not in ("development", "dev", "local"):
            await session.commit()
            print(
                f"ENVIRONMENT={settings.environment}: curriculum content seeded; "
                "dev school and dev accounts SKIPPED (only created when ENVIRONMENT is "
                "development, dev or local)."
            )
            return

        learner = await get_or_create_dev_learner(session)
        demo_school = await get_or_create_demo_school(session)
        demo_user = await get_or_create_demo_student_account(session, demo_school, learner)
        demo_teacher = await get_or_create_demo_teacher_account(session, demo_school)
        demo_principal = await ensure_dev_school_structure(session, demo_school, demo_teacher, learner)
        await ensure_dev_insights(session, demo_school)  # ADR-039
        await ensure_dev_parent(session, demo_school, learner)  # ADR-038

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
        print("Or log in as the teacher account (ADR-024 -- dashboard + bulk student provisioning):")
        print(f"  School:         {demo_school.name}  (id {demo_school.id})")
        print(f"  Staff number:   {demo_teacher.student_number}")
        print(f"  Password:       {DEV_TEACHER_PASSWORD}")
        print(f"  Teaches {DEV_ALLOCATION_SUBJECT[0]} (Grade {DEV_ALLOCATION_SUBJECT[1]}) to class {DEV_CLASS_NAME} (ADR-031)")
        print()
        print("Or log in as the principal (ADR-031 -- whole school, manages classes/staff):")
        print(f"  Staff number:   {demo_principal.student_number}")
        print(f"  Password:       {DEV_TEACHER_PASSWORD}")
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
