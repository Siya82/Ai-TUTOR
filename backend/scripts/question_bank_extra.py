"""
NEW 19 Nov 2026 (code review 19 Nov #15): more practice questions.

The original bank had 2 questions per topic, so "Send practice" (ADR-036)
and assignments soon repeated themselves. These add 3 per Mathematics topic
and 2 per Physical Sciences (physics) topic, in the same plain-text style
as seed_dev_data.py. seed_dev_data.py merges them into each topic's list;
ensure_questions() skips any that already exist, so re-seeding is safe.

Numeric answers are re-computed by tests/test_question_bank_extra.py.
CAPS Grades 10-12. Physics uses g = 9.8 m/s^2, h = 6.63 x 10^-34 J.s,
k = 9 x 10^9 N.m^2/C^2, G = 6.67 x 10^-11 N.m^2/kg^2, e = 1.6 x 10^-19 C.
"""

MATHS_G10 = {
    "Algebraic Expressions": [
        ("Factorise fully: x^2 - 9", "(x - 3)(x + 3)"),
        ("Factorise: x^2 + 5x + 6", "(x + 2)(x + 3)"),
        ("Simplify: (2x^2 - 8) / (x - 2)", "2(x + 2) = 2x + 4"),
    ],
    "Exponents": [
        ("Simplify: (3x^2)^3", "27x^6"),
        ("Simplify: 2^0 + 4^(-1)", "5/4 (1 1/4)"),
        ("Solve for x: 2^x = 16", "x = 4"),
    ],
    "Equations and Inequalities": [
        ("Solve for x: 3(x - 2) = 2x + 4", "x = 10"),
        ("Solve simultaneously: x + y = 7 and x - y = 1", "x = 4 and y = 3"),
        ("Solve for x: x^2 - 4x = 0", "x = 0 or x = 4"),
    ],
    "Number Patterns": [
        ("Find T_10 of the pattern 5, 9, 13, 17, ...", "T_10 = 41"),
        ("Which term of 2, 7, 12, 17, ... is equal to 97?", "The 20th term (n = 20)"),
        ("Find the nth-term formula for 20, 17, 14, 11, ...", "T_n = -3n + 23"),
    ],
    "Trigonometry": [
        ("In triangle ABC, angle B = 90 degrees, AB = 3 and BC = 4. Calculate AC.", "AC = 5"),
        ("Calculate without a calculator: sin^2(30) + cos^2(30)", "1"),
        ("Solve for theta (0 <= theta <= 90): 2cos(theta) = 1", "theta = 60 degrees"),
    ],
    "Functions": [
        ("Write down the y-intercept of y = 2x^2 - 8", "(0; -8)"),
        ("Find the x-intercepts of y = x^2 - 9", "(-3; 0) and (3; 0)"),
        ("For g(x) = 6/x, find g(-2)", "g(-2) = -3"),
    ],
    "Finance, Growth and Decay": [
        ("R5 000 is invested at 8% p.a. simple interest. Calculate the amount after 3 years.", "R6 200"),
        ("R2 000 is invested at 10% p.a. compounded annually. Calculate the amount after 3 years.", "R2 662"),
        ("A car worth R100 000 depreciates at 15% p.a. on a straight-line basis. Find its value after 4 years.",
         "R40 000"),
    ],
    "Analytical Geometry": [
        ("Calculate the distance between A(1; 2) and B(4; 6).", "AB = 5 units"),
        ("Find the gradient of the line 2y = 6x - 4.", "m = 3"),
        ("Line AB has gradient 2. What is the gradient of a line perpendicular to AB?", "-1/2"),
    ],
    "Euclidean Geometry": [
        ("A parallelogram has one interior angle of 70 degrees. Find the other three angles.",
         "110, 70 and 110 degrees"),
        ("At what angle do the diagonals of a rhombus meet?", "90 degrees (they bisect each other at right angles)"),
        ("In triangle ABC, D is the midpoint of AB and E is the midpoint of AC. BC = 12 cm. Find DE.",
         "DE = 6 cm (midpoint theorem)"),
    ],
    "Measurement": [
        ("Calculate the surface area of a cube with sides of 3 cm.", "54 cm^2"),
        ("Calculate the volume of a cylinder with radius 2 cm and height 7 cm (use pi = 22/7).", "88 cm^3"),
        ("Every side of a rectangular prism is doubled. By what factor does its volume change?", "8 times as large"),
    ],
    "Statistics": [
        ("Find the mode of 2, 4, 4, 5, 7, 4, 9", "4"),
        ("Find the range of 12, 5, 18, 9, 21", "16"),
        ("Find the interquartile range of 1, 3, 5, 7, 9, 11, 13, 15", "IQR = 12 - 4 = 8"),
    ],
    "Probability": [
        ("A fair coin is tossed twice. What is P(two heads)?", "1/4"),
        ("P(A) = 0.3 and P(B) = 0.5, and A and B are mutually exclusive. Find P(A or B).", "0.8"),
        ("If P(rain) = 0.35, what is P(no rain)?", "0.65"),
    ],
}

MATHS_G11 = {
    "Exponents and Surds": [
        ("Simplify: 8^(2/3)", "4"),
        ("Rationalise the denominator: 6 / sqrt(3)", "2*sqrt(3)"),
        ("Solve for x: 3^(x + 1) = 27", "x = 2"),
    ],
    "Equations and Inequalities": [
        ("Solve for x with the quadratic formula: x^2 + 2x - 4 = 0 (leave your answer in surd form)",
         "x = -1 + sqrt(5) or x = -1 - sqrt(5)"),
        ("Solve simultaneously: y = x + 1 and y = x^2 - 1", "x = 2, y = 3 or x = -1, y = 0"),
        ("For which value of k does x^2 + 4x + k = 0 have equal roots?", "k = 4"),
    ],
    "Number Patterns": [
        ("Find the next term of the quadratic pattern 3, 8, 15, 24, ...", "35"),
        ("Find T_n for the quadratic pattern 2, 6, 12, 20, ...", "T_n = n^2 + n"),
        ("The second difference of a quadratic pattern is 6. What is the coefficient of n^2 in T_n?", "3"),
    ],
    "Functions": [
        ("Write down the turning point of y = (x - 2)^2 + 3", "(2; 3)"),
        ("Write down the asymptotes of y = 1/(x - 1) + 2", "x = 1 and y = 2"),
        ("Find the axis of symmetry of y = x^2 - 6x + 5", "x = 3"),
    ],
    "Analytical Geometry": [
        ("Find the angle of inclination of a line with gradient 1.", "45 degrees"),
        ("Find the equation of the line through (2; 7) that is parallel to y = 3x - 1.", "y = 3x + 1"),
        ("Find the equation of the line through (1; 1) and (3; 5).", "y = 2x - 1"),
    ],
    "Trigonometry": [
        ("Simplify: sin(180 - x) / sin(x)", "1"),
        ("Find the general solution of sin(x) = 0.5", "x = 30 + k*360 or x = 150 + k*360, k an integer"),
        ("Simplify using an identity: 1 - sin^2(x)", "cos^2(x)"),
    ],
    "Euclidean Geometry": [
        ("The angle at the centre of a circle is 100 degrees. Find the angle at the circumference subtended by the same arc.",
         "50 degrees"),
        ("ABCD is a cyclic quadrilateral with angle A = 75 degrees. Find angle C.", "105 degrees"),
        ("What is the angle between a tangent and the radius at the point of contact?", "90 degrees"),
    ],
    "Measurement": [
        ("Calculate the volume of a cone with radius 3 cm and height 4 cm (leave in terms of pi).", "12*pi cm^3"),
        ("Calculate the volume of a sphere with radius 3 cm (leave in terms of pi).", "36*pi cm^3"),
        ("Calculate the surface area of a sphere with radius 5 cm (leave in terms of pi).", "100*pi cm^2"),
    ],
    "Finance, Growth and Decay": [
        ("Find the effective annual interest rate for 12% p.a. compounded monthly (as a %, to 2 decimals).", "12.68%"),
        ("A machine costs R50 000 and depreciates at 20% p.a. on the reducing balance. Find its value after 2 years.",
         "R32 000"),
        ("R10 000 grows to R14 641 in 4 years at i% p.a. compounded annually. Find i.", "i = 10%"),
    ],
    "Probability": [
        ("A and B are independent, P(A) = 0.4 and P(B) = 0.5. Find P(A and B).", "0.2"),
        ("P(A) = 0.6, P(B) = 0.3 and P(A and B) = 0.1. Find P(A or B).", "0.8"),
        ("A bag has 4 red and 6 blue balls. Two are drawn WITH replacement. Find P(both red).", "4/25 = 0.16"),
    ],
    "Statistics": [
        ("Find the variance of the data 2, 4, 6", "8/3 (about 2.67)"),
        ("Find the standard deviation of 5, 5, 5, 5", "0"),
        ("In a negatively skewed distribution, is the mean usually above or below the median?",
         "Below the median"),
    ],
}

MATHS_G12 = {
    "Sequences and Series": [
        ("Find the sum of the first 20 terms of 3 + 7 + 11 + ...", "S_20 = 820"),
        ("Find T_6 of the geometric sequence 2; 6; 18; ...", "T_6 = 486"),
        ("Find the sum to infinity of 8 + 4 + 2 + ...", "16"),
    ],
    "Functions and Inverse Functions": [
        ("Find the inverse of f(x) = 2x + 3", "f^-1(x) = (x - 3)/2"),
        ("Write down the inverse of y = 3^x in the form y = ...", "y = log_3(x)"),
        ("Find the inverse of f(x) = x^2 for x >= 0", "f^-1(x) = sqrt(x), x >= 0"),
    ],
    "Exponential and Logarithmic Functions": [
        ("Calculate: log_2(32)", "5"),
        ("Solve for x: log(x) = 2", "x = 100"),
        ("Solve for x, correct to 2 decimals: 5^x = 20", "x = 1.86"),
    ],
    "Finance, Growth and Decay": [
        ("R500 is saved at the end of every month for 2 years at 12% p.a. compounded monthly. Find the future value.",
         "R13 486.73"),
        ("Find the present value of R1 000 paid at the end of each month for 12 months at 12% p.a. compounded monthly.",
         "R11 255.08"),
        ("How many years does money take to double at 8% p.a. compounded annually (to 2 decimals)?",
         "9.01 years"),
    ],
    "Trigonometry: Compound Angles": [
        ("Expand: sin(A + B)", "sin(A)cos(B) + cos(A)sin(B)"),
        ("Simplify: cos^2(x) - sin^2(x)", "cos(2x)"),
        ("If sin(x) = 3/5 and x is acute, find sin(2x) without a calculator.", "24/25"),
    ],
    "Trigonometry: 2D and 3D Problems": [
        ("In triangle ABC, a = 10, angle A = 30 degrees and angle B = 45 degrees. Find b (2 decimals).", "b = 14.14"),
        ("In triangle ABC, a = 5, b = 7 and angle C = 60 degrees. Find c (2 decimals).", "c = 6.24"),
        ("Find the area of triangle ABC with a = 6, b = 8 and angle C = 30 degrees.", "12 square units"),
    ],
    "Polynomials": [
        ("Find the remainder when x^3 - 2x + 1 is divided by x - 2.", "5"),
        ("Factorise fully: x^3 - 6x^2 + 11x - 6", "(x - 1)(x - 2)(x - 3)"),
        ("Find k if x + 1 is a factor of x^3 + kx + 3.", "k = 2"),
    ],
    "Differential Calculus": [
        ("Differentiate: f(x) = 3x^4 - 2x + 5", "f'(x) = 12x^3 - 2"),
        ("Find the gradient of the tangent to y = x^2 at x = 3.", "6"),
        ("Find the turning points of y = x^3 - 3x.", "(-1; 2) a local maximum and (1; -2) a local minimum"),
    ],
    "Analytical Geometry": [
        ("Find the centre and radius of x^2 + y^2 - 4x + 6y - 3 = 0.", "Centre (2; -3), radius 4"),
        ("Write the equation of the circle with centre at the origin that passes through (3; 4).", "x^2 + y^2 = 25"),
        ("Find the equation of the tangent to x^2 + y^2 = 25 at the point (3; 4).", "y = -3/4 x + 25/4"),
    ],
    "Euclidean Geometry": [
        ("In triangle ABC, DE is parallel to BC with D on AB and E on AC. AD = 4, DB = 6 and AE = 6. Find EC.",
         "EC = 9"),
        ("Two similar triangles have corresponding sides in the ratio 2 : 3. What is the ratio of their areas?",
         "4 : 9"),
        ("In triangle ABC, angle A = 90 degrees and AD is perpendicular to BC. BD = 4 and DC = 9. Find AD.",
         "AD = 6"),
    ],
    "Statistics: Regression and Correlation": [
        ("What does a correlation coefficient of r = -0.92 tell you?", "A strong negative linear correlation"),
        ("The least-squares line is y = 2.5x + 10. Predict y when x = 8.", "y = 30"),
        ("What value of r shows no linear correlation at all?", "r = 0"),
    ],
    "Counting and Probability": [
        ("In how many ways can the letters of the word MATHS be arranged?", "5! = 120"),
        ("In how many ways can the letters of the word APPLE be arranged?", "5!/2! = 60"),
        ("How many 4-digit codes can be made from the digits 0-9 if no digit may repeat?", "10 x 9 x 8 x 7 = 5 040"),
    ],
}

PHYSICS_G10 = {
    "Vectors in Two Dimensions": [
        ("Find the resultant of 3 N east and 4 N north.", "5 N at 53.13 degrees north of east"),
        ("Forces of 10 N east and 4 N west act on an object. Find the resultant.", "6 N east"),
    ],
    "Motion in One Dimension": [
        ("A car starts from rest and accelerates at 2 m/s^2 for 5 s. Find its final velocity.", "10 m/s"),
        ("The same car (from rest, 2 m/s^2, 5 s): how far does it travel?", "25 m"),
    ],
    "Mechanical Energy": [
        ("Calculate the gravitational potential energy of a 2 kg object 5 m above the ground.", "98 J"),
        ("Calculate the kinetic energy of a 4 kg object moving at 3 m/s.", "18 J"),
    ],
    "Waves, Sound and Light": [
        ("A wave has a frequency of 50 Hz and a wavelength of 2 m. Calculate its speed.", "100 m/s"),
        ("A wave has a frequency of 4 Hz. Calculate its period.", "0.25 s"),
    ],
    "Electromagnetic Radiation": [
        ("Calculate the energy of a photon of frequency 5 x 10^14 Hz.", "3.32 x 10^-19 J"),
        ("Which carries more energy per photon: ultraviolet or infrared radiation?", "Ultraviolet (higher frequency)"),
    ],
    "Magnetism": [
        ("What happens when two unlike magnetic poles are brought close together?", "They attract each other"),
        ("In which direction do magnetic field lines point outside a bar magnet?", "From the north pole to the south pole"),
    ],
    "Electrostatics": [
        ("How many electrons make up a charge of -2 nC?", "1.25 x 10^10 electrons"),
        ("Identical spheres with charges +6 nC and -2 nC touch and are separated. Find the charge on each.",
         "+2 nC each"),
    ],
}

PHYSICS_G11 = {
    "Vectors in Two Dimensions": [
        ("A 20 N force acts at 30 degrees above the horizontal. Find its horizontal component (2 decimals).",
         "17.32 N"),
        ("The same 20 N force at 30 degrees above the horizontal: find its vertical component.", "10 N"),
    ],
    "Newton's Laws": [
        ("A net force of 20 N acts on a 5 kg object. Calculate its acceleration.", "4 m/s^2"),
        ("Calculate the weight of a 60 kg learner on Earth.", "588 N"),
    ],
    "Newton's Universal Law of Gravitation": [
        ("If the distance between two masses is doubled, what happens to the gravitational force between them?",
         "It becomes a quarter of the original force"),
        ("Calculate the gravitational force between two 1 000 kg masses 2 m apart.", "1.67 x 10^-5 N"),
    ],
    "Electrostatics": [
        ("Calculate the force between charges of +2 uC and +3 uC that are 0.3 m apart.", "0.6 N, repulsive"),
        ("Calculate the electric field strength 0.2 m from a 4 uC point charge.", "9 x 10^5 N/C"),
    ],
    "Electromagnetism": [
        ("A coil of 100 turns has its magnetic flux change by 0.02 Wb in 0.1 s. Calculate the induced emf.", "20 V"),
        ("State Lenz's law in words.", "The induced current flows in a direction that opposes the change in magnetic flux that caused it"),
    ],
    "Electric Circuits": [
        ("A potential difference of 12 V is applied across a 4 ohm resistor. Calculate the current.", "3 A"),
        ("Calculate the total resistance of a 6 ohm and a 3 ohm resistor connected in parallel.", "2 ohm"),
    ],
}

PHYSICS_G12 = {
    "Momentum and Impulse": [
        ("Calculate the momentum of a 1 500 kg car moving at 20 m/s.", "30 000 kg.m/s"),
        ("A force of 200 N acts on a ball for 0.05 s. Calculate the impulse.", "10 N.s"),
    ],
    "Vertical Projectile Motion": [
        ("A ball is thrown straight up at 19.6 m/s. How long does it take to reach its highest point?", "2 s"),
        ("The same ball (thrown up at 19.6 m/s): find its maximum height.", "19.6 m"),
    ],
    "Work, Energy and Power": [
        ("A 50 N force moves an object 4 m in the direction of the force. Calculate the work done.", "200 J"),
        ("A motor does 600 J of work in 30 s. Calculate its average power.", "20 W"),
    ],
    "Doppler Effect": [
        ("A sound source moves towards a stationary listener. Is the observed frequency higher or lower?", "Higher"),
        ("A 500 Hz source moves at 20 m/s towards a stationary listener. The speed of sound is 340 m/s. Find the observed frequency.",
         "531.25 Hz"),
    ],
    "Electric Circuits": [
        ("A battery has emf 12 V and internal resistance 0.5 ohm, connected to a 5.5 ohm resistor. Find the current.",
         "2 A"),
        ("For the same circuit (12 V, 0.5 ohm internal, 5.5 ohm external), find the terminal potential difference.",
         "11 V"),
    ],
    "Electrodynamics": [
        ("The peak voltage of an AC supply is 340 V. Calculate the rms voltage.", "240.42 V"),
        ("What energy conversion takes place in a generator?", "Mechanical (kinetic) energy to electrical energy"),
    ],
    "Photoelectric Effect": [
        ("A metal has a work function of 3.2 x 10^-19 J. Calculate its threshold frequency.", "4.83 x 10^14 Hz"),
        ("Light above the threshold frequency is made brighter. What happens to the emitted electrons?",
         "More electrons are emitted per second; their maximum kinetic energy stays the same"),
    ],
}

from scripts.chemistry_content import (  # noqa: E402  ADR-046
    CHEM_QUESTIONS_G10,
    CHEM_QUESTIONS_G11,
    CHEM_QUESTIONS_G12,
    PHYSICS_QUESTIONS_G11_EXTRA,
)

# (subject name, grade) -> extra questions per topic, merged by seed_dev_data.py
EXTRA_QUESTIONS = {
    ("Pure Mathematics", 10): MATHS_G10,
    ("Pure Mathematics", 11): MATHS_G11,
    ("Pure Mathematics", 12): MATHS_G12,
    ("Physical Sciences", 10): {**PHYSICS_G10, **CHEM_QUESTIONS_G10},
    ("Physical Sciences", 11): {**PHYSICS_G11, **PHYSICS_QUESTIONS_G11_EXTRA, **CHEM_QUESTIONS_G11},
    ("Physical Sciences", 12): {**PHYSICS_G12, **CHEM_QUESTIONS_G12},
}
