"""
Text for the one-minute "What is this topic?" videos (ADR-049).

One entry per topic. A teacher should check each entry before its video
is shown to learners: set "reviewed_by" when they have. Maths goes in
$...$ (KaTeX). Keep sentences short: learners read these at video speed.

Fields
  what     one or two sentences: what the topic is
  visual   one formula or line shown big beside "what" (optional)
  why      why it matters
  where    three everyday South African places you meet it
  who      careers that use it
  paper    which final exam paper it's in
  how      a worked example: {"q": question, "steps": [...], "a": answer}
  say      how the narrator says lines that contain maths (ADR-049 voice):
           "q", "steps", "a", and "where" ({index: text}). Lines without
           maths are spoken as written.

"Builds on" and "leads to" come from the topic prerequisites in the seed,
so they always match what THUTOra's tutor uses.
"""

GRADE10_MATHS = {
    "Algebraic Expressions": {
        "what": "Using letters to stand for numbers, then simplifying, expanding and factorising the expressions you build.",
        "visual": r"(x+3)(x-2) = x^2 + x - 6",
        "why": "Algebra is the language of maths. Almost every topic in Grades 10 to 12 is written in it.",
        "where": [
            r"A cellphone bill: R99 plus R1.50 a minute is $99 + 1{,}5m$",
            "Formulas in a spreadsheet",
            "Working out the floor area of a room on a building plan",
        ],
        "who": ["Engineers", "Programmers", "Actuaries", "Economists"],
        "paper": "Paper 1",
        "say": {  # spoken versions of lines with maths in them (ADR-049 voice)
            "where": {0: "A cellphone bill: ninety-nine rand, plus one rand fifty a minute."},
            "q": "Factorise x squared, minus five x, plus six.",
            "steps": [
                "Find two numbers that multiply to six, and add to negative five.",
                "They are negative two, and negative three.",
                "So it factorises as x minus two, times x minus three.",
            ],
            "a": "Check by expanding: you get x squared, minus five x, plus six. Correct.",
        },
        "how": {
            "q": r"Factorise $x^2 - 5x + 6$",
            "steps": [
                r"Find two numbers that multiply to $6$ and add to $-5$",
                r"They are $-2$ and $-3$",
                r"So $x^2 - 5x + 6 = (x-2)(x-3)$",
            ],
            "a": r"Check by expanding: $(x-2)(x-3) = x^2 - 5x + 6$ ✓",
        },
    },
    "Exponents": {
        "what": "A power is a short way to write repeated multiplication. The exponent laws tell you how to work with powers.",
        "visual": r"2^5 = 2 \times 2 \times 2 \times 2 \times 2 = 32",
        "why": "Exponents describe anything that doubles, grows or shrinks by a percentage, and very large or very small numbers.",
        "where": [
            "Phone memory sizes: 16, 32, 64, 128 GB",
            "Bacteria doubling every hour",
            r"The Sun is about $1{,}5 \times 10^{8}$ km away",
        ],
        "who": ["Scientists", "Computer scientists", "Financial analysts", "Health researchers"],
        "paper": "Paper 1",
        "say": {  # spoken versions of lines with maths in them (ADR-049 voice)
            "where": {0: "Phone memory sizes: sixteen, thirty-two, sixty-four, and a hundred and twenty-eight gigabytes.", 2: "The Sun is about a hundred and fifty million kilometres away. That's one comma five, times ten to the power eight."},
            "q": "Simplify: two to the power x plus two, times two to the power x, all over two to the power two x.",
            "steps": [
                "Same base, multiplying: add the exponents. That gives two to the power two x plus two.",
                "Same base, dividing: subtract the exponents. That leaves two to the power two.",
            ],
            "a": "And two squared is four.",
        },
        "how": {
            "q": r"Simplify $\dfrac{2^{x+2} \cdot 2^{x}}{2^{2x}}$",
            "steps": [
                r"Same base, multiplying: add the exponents. $2^{x+2} \cdot 2^{x} = 2^{2x+2}$",
                r"Same base, dividing: subtract the exponents. $2^{2x+2-2x} = 2^{2}$",
            ],
            "a": r"$2^{2} = 4$",
        },
    },
    "Equations and Inequalities": {
        "what": "Finding the value that makes a statement true: linear, quadratic and simultaneous equations, and linear inequalities.",
        "visual": r"3x - 4 = 11 \;\Rightarrow\; x = 5",
        "why": "Solving for an unknown is how maths answers real questions.",
        "where": [
            "How many data bundles fit in your budget",
            "When a tuck shop starts making a profit",
            "Comparing two cellphone contracts",
        ],
        "who": ["Engineers", "Accountants", "Pharmacists", "Logistics planners"],
        "paper": "Paper 1",
        "say": {  # spoken versions of lines with maths in them (ADR-049 voice)
            "q": "Solve: two minus three x is less than or equal to eleven.",
            "steps": [
                "Subtract two from both sides: negative three x is less than or equal to nine.",
                "Now divide by negative three. Dividing by a negative flips the sign, so x is greater than or equal to negative three.",
            ],
            "a": "So x is greater than or equal to negative three.",
        },
        "how": {
            "q": r"Solve $2 - 3x \leq 11$",
            "steps": [
                r"Subtract $2$ from both sides: $-3x \leq 9$",
                r"Divide by $-3$. Dividing by a negative flips the sign: $x \geq -3$",
            ],
            "a": r"$x \geq -3$",
        },
    },
    "Number Patterns": {
        "what": "Sequences of numbers that follow a rule. In Grade 10 the pattern goes up or down by the same amount each time.",
        "visual": r"3;\ 7;\ 11;\ 15;\ \ldots \qquad T_n = 4n - 1",
        "why": "Once you know the rule, you can find any term without writing out the whole list.",
        "where": [
            "Saving R50 more every week",
            "Seats in a stadium: each row has two more",
            "Tiles or matchsticks in a growing shape",
        ],
        "who": ["Data analysts", "Programmers", "Scientists"],
        "paper": "Paper 1",
        "say": {  # spoken versions of lines with maths in them (ADR-049 voice)
            "q": "Find the general term, and the fiftieth term, of five, eight, eleven, fourteen, and so on.",
            "steps": [
                "It goes up by three each time, so T n equals three n, plus c.",
                "The first term is five, so three plus c equals five, and c is two.",
                "So T n equals three n, plus two.",
            ],
            "a": "The fiftieth term is three times fifty, plus two. That's one hundred and fifty-two.",
        },
        "how": {
            "q": r"Find $T_n$ and $T_{50}$ for $5;\ 8;\ 11;\ 14;\ \ldots$",
            "steps": [
                r"It goes up by $3$ each time, so $T_n = 3n + c$",
                r"$T_1 = 5$: $3(1) + c = 5$, so $c = 2$",
                r"$T_n = 3n + 2$",
            ],
            "a": r"$T_{50} = 3(50) + 2 = 152$",
        },
    },
    "Trigonometry": {
        "what": "The ratios between the sides of a right-angled triangle: sine, cosine and tangent. You use them to find unknown sides and angles.",
        "visual": r"\sin\theta = \frac{\text{opp}}{\text{hyp}} \quad \cos\theta = \frac{\text{adj}}{\text{hyp}} \quad \tan\theta = \frac{\text{opp}}{\text{adj}}",
        "why": "It lets you measure things you can't reach, from one distance and one angle.",
        "where": [
            "The height of a tree or a building",
            "A safe slope for a wheelchair ramp",
            "The pitch of a roof",
        ],
        "who": ["Architects", "Surveyors", "Pilots", "Engineers"],
        "paper": "Paper 2",
        "say": {  # spoken versions of lines with maths in them (ADR-049 voice)
            "q": "A five metre ladder leans against a wall, at sixty degrees to the ground. How high up the wall does it reach?",
            "steps": [
                "The ladder is the hypotenuse, and the height is opposite the sixty degree angle.",
                "So sine sixty degrees equals h over five, which means h equals five, times sine sixty degrees.",
            ],
            "a": "h is about four comma three three metres.",
        },
        "how": {
            "q": r"A $5$ m ladder leans against a wall at $60^\circ$ to the ground. How high up the wall does it reach?",
            "steps": [
                r"The ladder is the hypotenuse; the height is opposite the $60^\circ$ angle",
                r"$\sin 60^\circ = \dfrac{h}{5}$, so $h = 5 \sin 60^\circ$",
            ],
            "a": r"$h \approx 4{,}33$ m",
        },
    },
    "Functions": {
        "what": "A function is a rule that gives exactly one output for each input. In Grade 10: straight lines, parabolas, hyperbolas and exponential graphs.",
        "visual": r"y = ax + q \quad y = ax^2 + q \quad y = \frac{a}{x} + q \quad y = ab^x + q",
        "why": "Functions describe how one thing changes with another, and graphs let you see it.",
        "where": [
            "An electricity bill that grows with the units you use",
            "The path of a ball you throw",
            "Sharing a prize: more friends, smaller shares",
        ],
        "who": ["Economists", "Engineers", "Data scientists"],
        "paper": "Paper 1",
        "say": {  # spoken versions of lines with maths in them (ADR-049 voice)
            "q": "Find the key points of y equals x squared, minus four.",
            "steps": [
                "The y-intercept: put x equal to zero, and y is negative four.",
                "The x-intercepts: x squared minus four equals zero, so x is plus or minus two.",
                "a is positive, so the graph opens upward, with its turning point at zero, negative four.",
            ],
            "a": "A U-shaped parabola, through negative two, zero; zero, negative four; and two, zero.",
        },
        "how": {
            "q": r"Sketch the key points of $y = x^2 - 4$",
            "steps": [
                r"$y$-intercept: put $x = 0$, so $y = -4$",
                r"$x$-intercepts: $x^2 - 4 = 0$, so $x = \pm 2$",
                r"$a > 0$, so it opens upward with turning point $(0;\,-4)$",
            ],
            "a": r"A ∪-shaped parabola through $(-2;\,0)$, $(0;\,-4)$ and $(2;\,0)$",
        },
    },
    "Finance, Growth and Decay": {
        "what": "How money grows or shrinks over time: simple and compound interest, hire purchase, inflation and exchange rates.",
        "visual": r"A = P(1 + in) \qquad A = P(1 + i)^n",
        "why": "Every adult borrows, saves and pays prices that rise. This topic shows you what that really costs.",
        "where": [
            "A savings account or a stokvel",
            "Buying a fridge on hire purchase",
            "Changing rand to dollars for a trip",
        ],
        "who": ["Bankers", "Accountants", "Financial planners", "Everyone with money"],
        "paper": "Paper 1",
        "say": {  # spoken versions of lines with maths in them (ADR-049 voice)
            "q": "Five thousand rand is invested at eight percent per year, compound interest, for three years. What is it worth?",
            "steps": [
                "Use A equals P, times one plus i, to the power n. P is five thousand, i is zero comma zero eight, and n is three.",
                "So A equals five thousand, times one comma zero eight, cubed.",
            ],
            "a": "That's six thousand, two hundred and ninety-eight rand, fifty-six. Simple interest would give only six thousand, two hundred rand.",
        },
        "how": {
            "q": r"R5 000 is invested at $8\%$ per year, compound interest, for $3$ years. What is it worth?",
            "steps": [
                r"$A = P(1 + i)^n$ with $P = 5\,000$, $i = 0{,}08$, $n = 3$",
                r"$A = 5\,000(1{,}08)^3$",
            ],
            "a": r"$A = \text{R}6\,298{,}56$ (simple interest would give R6 200)",
        },
    },
    "Analytical Geometry": {
        "what": "Geometry on the Cartesian plane. You use coordinates to find distances, midpoints and gradients.",
        "visual": r"d = \sqrt{(x_2 - x_1)^2 + (y_2 - y_1)^2}",
        "why": "It turns shapes into numbers, so a computer or a calculator can work with them.",
        "where": [
            "Maps and GPS on your phone",
            "Characters moving in a video game",
            "How steep a road is (its gradient)",
        ],
        "who": ["GIS analysts", "Game developers", "Civil engineers"],
        "paper": "Paper 2",
        "say": {  # spoken versions of lines with maths in them (ADR-049 voice)
            "q": "A is the point one, two, and B is seven, ten. Find the length A B, the midpoint, and the gradient.",
            "steps": [
                "A B is the square root of six squared plus eight squared. That's the square root of a hundred, which is ten.",
                "The midpoint is the average of the coordinates: four, six.",
                "The gradient is the change in y over the change in x: eight over six, which is four thirds.",
            ],
            "a": "So A B is ten, the midpoint is four, six, and the gradient is four thirds.",
        },
        "how": {
            "q": r"$A(1;\,2)$ and $B(7;\,10)$. Find $AB$, the midpoint and the gradient.",
            "steps": [
                r"$AB = \sqrt{6^2 + 8^2} = \sqrt{100} = 10$",
                r"Midpoint $= \left(\dfrac{1+7}{2};\ \dfrac{2+10}{2}\right) = (4;\,6)$",
                r"Gradient $= \dfrac{10 - 2}{7 - 1} = \dfrac{8}{6} = \dfrac{4}{3}$",
            ],
            "a": r"$AB = 10$, midpoint $(4;\,6)$, gradient $\tfrac{4}{3}$",
        },
    },
    "Euclidean Geometry": {
        "what": "The properties of lines, triangles and quadrilaterals, and proving them step by step with a reason for each statement.",
        "visual": r"\text{Statement} \;\;|\;\; \text{Reason}",
        "why": "It trains you to argue logically: every claim needs a reason.",
        "where": [
            "Roof trusses made of triangles",
            "Floor tiles that fit together",
            "A scissor lift: its parallelograms keep the platform level",
        ],
        "who": ["Architects", "Engineers", "Carpenters", "Designers"],
        "paper": "Paper 2",
        "say": {  # spoken versions of lines with maths in them (ADR-049 voice)
            "q": "In triangle A B C, D and E are the midpoints of A B and A C. B C is twelve centimetres. Find D E.",
            "steps": [
                "D and E are the midpoints of two sides of the triangle.",
                "The midpoint theorem says D E is parallel to B C, and half as long.",
            ],
            "a": "So D E is six centimetres. Reason: the midpoint theorem.",
        },
        "how": {
            "q": r"In $\triangle ABC$, $D$ and $E$ are the midpoints of $AB$ and $AC$. $BC = 12$ cm. Find $DE$.",
            "steps": [
                r"$D$ and $E$ are midpoints of two sides of the triangle",
                r"Midpoint theorem: $DE \parallel BC$ and $DE = \tfrac{1}{2}BC$",
            ],
            "a": r"$DE = 6$ cm  (reason: midpoint theorem)",
        },
    },
    "Measurement": {
        "what": "Surface area and volume of 3D shapes: prisms, cylinders, pyramids, cones and spheres.",
        "visual": r"V_{\text{cylinder}} = \pi r^2 h",
        "why": "It tells you how much something holds, and how much material it takes to make or cover it.",
        "where": [
            "How much water a JoJo tank holds",
            "How much paint a wall or a tank needs",
            "Designing a box or a tin",
        ],
        "who": ["Builders", "Quantity surveyors", "Manufacturers"],
        "paper": "Paper 2",
        "say": {  # spoken versions of lines with maths in them (ADR-049 voice)
            "q": "A cylindrical tank has a radius of zero comma five metres, and a height of two metres. How much water does it hold?",
            "steps": [
                "Volume equals pi r squared h: pi, times zero comma five squared, times two.",
                "That's about one comma five seven cubic metres. And one cubic metre holds a thousand litres.",
            ],
            "a": "So it holds about one thousand, five hundred and seventy litres.",
        },
        "how": {
            "q": r"A cylindrical tank has radius $0{,}5$ m and height $2$ m. How much water does it hold?",
            "steps": [
                r"$V = \pi r^2 h = \pi (0{,}5)^2 (2)$",
                r"$V \approx 1{,}57$ m³, and $1$ m³ $= 1\,000$ litres",
            ],
            "a": r"About $1\,570$ litres",
        },
    },
    "Statistics": {
        "what": "Collecting, organising and summarising data: mean, median, mode, range, quartiles and box-and-whisker plots.",
        "visual": r"\bar{x} = \frac{\text{sum of values}}{\text{number of values}}",
        "why": "Data is everywhere. Statistics helps you see the story in it and spot claims that don't add up.",
        "where": [
            "Your class's test results",
            "Rainfall over a year",
            "Census figures from Stats SA",
        ],
        "who": ["Statisticians", "Health researchers", "Sports analysts", "Marketers"],
        "paper": "Paper 2",
        "say": {  # spoken versions of lines with maths in them (ADR-049 voice)
            "q": "Find the mean, median and range of three, five, seven, eight and twelve.",
            "steps": [
                "The mean: add them to get thirty-five, and divide by five. That's seven.",
                "The median: the middle value of the ordered list is seven.",
                "The range: twelve minus three is nine.",
            ],
            "a": "Mean seven, median seven, range nine.",
        },
        "how": {
            "q": r"Find the mean, median and range of $3;\ 5;\ 7;\ 8;\ 12$",
            "steps": [
                r"Mean $= \dfrac{3 + 5 + 7 + 8 + 12}{5} = \dfrac{35}{5} = 7$",
                r"Median: the middle value of the ordered list is $7$",
                r"Range $= 12 - 3 = 9$",
            ],
            "a": r"Mean $7$, median $7$, range $9$",
        },
    },
    "Probability": {
        "what": "How likely something is to happen, from 0 (impossible) to 1 (certain), using sample spaces and Venn diagrams.",
        "visual": r"P(E) = \frac{\text{number of favourable outcomes}}{\text{total number of outcomes}}",
        "why": "It helps you make decisions when you can't be sure of the result.",
        "where": [
            "Weather forecasts: a 70% chance of rain",
            "Insurance premiums",
            "Board games and the Lotto",
        ],
        "who": ["Actuaries", "Insurers", "Meteorologists", "Doctors"],
        "paper": "Paper 1",
        "say": {  # spoken versions of lines with maths in them (ADR-049 voice)
            "where": {0: "Weather forecasts: a seventy percent chance of rain."},
            "q": "A bag has three red and five blue marbles. Find the probability of red, and of not red.",
            "steps": [
                "There are eight marbles, and three are red, so the probability of red is three eighths.",
                "Not red is the complement: one minus three eighths.",
            ],
            "a": "So the probability of red is three eighths, and of not red, five eighths.",
        },
        "how": {
            "q": r"A bag has $3$ red and $5$ blue marbles. Find $P(\text{red})$ and $P(\text{not red})$.",
            "steps": [
                r"There are $8$ marbles, and $3$ are red: $P(\text{red}) = \dfrac{3}{8}$",
                r"Not red is the complement: $P(\text{not red}) = 1 - \dfrac{3}{8}$",
            ],
            "a": r"$P(\text{red}) = \tfrac{3}{8}$, $P(\text{not red}) = \tfrac{5}{8}$",
        },
    },
}

# (subject name in the seed, grade) -> content
CONTENT = {
    ("Pure Mathematics", 10): GRADE10_MATHS,
}
