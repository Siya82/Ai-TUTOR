"""
Text for the topic induction videos (ADR-049, reworked 22 Nov 2026).

Each video introduces a topic a learner is about to start:
  welcome -> what it's about (and why) -> what to expect -> where it comes
  from (previous grade, and links in this grade) -> example 1 (a basic
  warm-up) -> example 2 (exam style) -> ready?

One entry per topic. A teacher should check each entry before its video
is shown to learners: set "reviewed_by" when they have. Maths goes in
$...$ (KaTeX). Keep sentences short: learners read these at video speed.

Fields
  what      one or two sentences: what the topic is about
  visual    one formula shown big beside "what" (optional)
  why       one sentence: why it matters
  expect    4-6 things the learner will learn (plain text, no maths)
  previous  what it builds on from the previous grade (CAPS); for Grade 10
            that's Grade 9 Senior Phase work, which THUTOra doesn't hold
  paper     which final exam paper it's in
  examples  two worked examples, basic first:
            {"q", "steps": [...], "a", "say": {"q", "steps", "a"}}
            "say" is how the narrator reads the maths (for the voice)

Links within THUTOra ("in this grade it uses", "leads to") come from the
topic prerequisites in the seed, so they always match the tutor.
"""

GRADE10_MATHS = {
    "Algebraic Expressions": {
        "what": "Using letters to stand for numbers, then simplifying, expanding and factorising the expressions you build.",
        "visual": "(x+3)(x-2) = x^2 + x - 6",
        "why": "Algebra is the language of maths. Almost every topic in Grades 10 to 12 is written in it.",
        "expect": [
            "The real number system: rational and irrational numbers",
            "Rounding off, and estimating surds",
            "Multiplying binomials and trinomials",
            "Factorising: common factors, difference of squares, trinomials, grouping, sum and difference of cubes",
            "Simplifying algebraic fractions",
        ],
        "previous": [
            "Grade 9 Algebraic expressions: expanding brackets and simple factorising",
            "Grade 9 Numbers: integers, rational numbers and square roots",
        ],
        "paper": "Paper 1",
        "examples": [
            {
                "q": "Simplify $3(x + 4) - 2x$",
                "steps": [
                    "Multiply $3$ into the bracket: $3x + 12 - 2x$",
                    "Collect like terms: $3x - 2x = x$",
                ],
                "a": "$x + 12$",
                "say": {
                    "q": "Simplify three, times x plus four, minus two x.",
                    "steps": [
                        "Multiply three into the bracket: three x, plus twelve, minus two x.",
                        "Collect like terms: three x minus two x is x.",
                    ],
                    "a": "So the answer is x plus twelve.",
                },
            },
            {
                "q": "Factorise $x^2 - 5x + 6$",
                "steps": [
                    "Find two numbers that multiply to $6$ and add to $-5$",
                    "They are $-2$ and $-3$",
                    "So $x^2 - 5x + 6 = (x-2)(x-3)$",
                ],
                "a": "Check by expanding: $(x-2)(x-3) = x^2 - 5x + 6$ ✓",
                "say": {
                    "q": "Factorise x squared, minus five x, plus six.",
                    "steps": [
                        "Find two numbers that multiply to six, and add to negative five.",
                        "They are negative two, and negative three.",
                        "So it factorises as x minus two, times x minus three.",
                    ],
                    "a": "Check by expanding: you get x squared, minus five x, plus six. Correct.",
                },
            },
        ],
    },
    "Exponents": {
        "what": "A power is a short way to write repeated multiplication. The exponent laws tell you how to work with powers.",
        "visual": r"2^5 = 2 \times 2 \times 2 \times 2 \times 2 = 32",
        "why": "Exponents describe anything that doubles, grows or shrinks by a percentage, and very large or very small numbers.",
        "expect": [
            "The laws of exponents",
            "Zero and negative exponents",
            "Rational (fraction) exponents and surds",
            "Simplifying expressions with powers",
            "Solving simple exponential equations",
        ],
        "previous": [
            "Grade 9 Exponents: the laws for whole-number powers",
            "Grade 9 Scientific notation",
        ],
        "paper": "Paper 1",
        "examples": [
            {
                "q": r"Simplify $2^3 \times 2^2$",
                "steps": [
                    "Same base, multiplying: add the exponents",
                    "$2^{3+2} = 2^5$",
                ],
                "a": "$2^5 = 32$",
                "say": {
                    "q": "Simplify two cubed, times two squared.",
                    "steps": [
                        "Same base, multiplying: add the exponents.",
                        "Three plus two is five, so it's two to the power five.",
                    ],
                    "a": "And two to the power five is thirty-two.",
                },
            },
            {
                "q": r"Simplify $\dfrac{2^{x+2} \cdot 2^{x}}{2^{2x}}$",
                "steps": [
                    r"Same base, multiplying: add the exponents. $2^{x+2} \cdot 2^{x} = 2^{2x+2}$",
                    "Same base, dividing: subtract the exponents. $2^{2x+2-2x} = 2^{2}$",
                ],
                "a": "$2^{2} = 4$",
                "say": {
                    "q": "Simplify: two to the power x plus two, times two to the power x, all over two to the power two x.",
                    "steps": [
                        "Same base, multiplying: add the exponents. That gives two to the power two x plus two.",
                        "Same base, dividing: subtract the exponents. That leaves two to the power two.",
                    ],
                    "a": "And two squared is four.",
                },
            },
        ],
    },
    "Equations and Inequalities": {
        "what": "Finding the value that makes a statement true: linear, quadratic and simultaneous equations, and linear inequalities.",
        "visual": r"3x - 4 = 11 \;\Rightarrow\; x = 5",
        "why": "Solving for an unknown is how maths answers real questions.",
        "expect": [
            "Linear equations",
            "Quadratic equations, solved by factorising",
            "Literal equations: changing the subject of a formula",
            "Simultaneous linear equations",
            "Linear inequalities on a number line",
            "Word problems",
        ],
        "previous": [
            "Grade 9 Algebraic equations: solving linear equations",
            "Grade 9 Algebraic expressions: factorising",
        ],
        "paper": "Paper 1",
        "examples": [
            {
                "q": "Solve $2x + 5 = 17$",
                "steps": [
                    "Subtract $5$ from both sides: $2x = 12$",
                    "Divide both sides by $2$: $x = 6$",
                ],
                "a": "$x = 6$. Check: $2(6) + 5 = 17$ ✓",
                "say": {
                    "q": "Solve two x plus five equals seventeen.",
                    "steps": [
                        "Subtract five from both sides: two x equals twelve.",
                        "Divide both sides by two: x equals six.",
                    ],
                    "a": "x is six. Check: two times six, plus five, is seventeen. Correct.",
                },
            },
            {
                "q": r"Solve $2 - 3x \leq 11$",
                "steps": [
                    r"Subtract $2$ from both sides: $-3x \leq 9$",
                    r"Divide by $-3$. Dividing by a negative flips the sign: $x \geq -3$",
                ],
                "a": r"$x \geq -3$",
                "say": {
                    "q": "Solve: two minus three x is less than or equal to eleven.",
                    "steps": [
                        "Subtract two from both sides: negative three x is less than or equal to nine.",
                        "Now divide by negative three. Dividing by a negative flips the sign, so x is greater than or equal to negative three.",
                    ],
                    "a": "So x is greater than or equal to negative three.",
                },
            },
        ],
    },
    "Number Patterns": {
        "what": "Sequences of numbers that follow a rule. In Grade 10 the pattern goes up or down by the same amount each time.",
        "visual": r"3;\ 7;\ 11;\ 15;\ \ldots \qquad T_n = 4n - 1",
        "why": "Once you know the rule, you can find any term without writing out the whole list.",
        "expect": [
            "Patterns that go up or down by the same amount",
            "Finding the common difference",
            "Writing the general term of a pattern",
            "Finding a term from its position, and a position from a term",
        ],
        "previous": [
            "Grade 9 Numeric and geometric patterns",
            "Grade 9 Functions and relationships: input and output",
        ],
        "paper": "Paper 1",
        "examples": [
            {
                "q": r"Write the next two terms: $4;\ 9;\ 14;\ 19;\ \ldots$",
                "steps": [
                    "Each term is $5$ more than the one before",
                    "$19 + 5 = 24$ and $24 + 5 = 29$",
                ],
                "a": r"$24;\ 29$",
                "say": {
                    "q": "Write the next two terms of four, nine, fourteen, nineteen, and so on.",
                    "steps": [
                        "Each term is five more than the one before.",
                        "Nineteen plus five is twenty-four, and twenty-four plus five is twenty-nine.",
                    ],
                    "a": "The next two terms are twenty-four and twenty-nine.",
                },
            },
            {
                "q": r"Find $T_n$ and $T_{50}$ for $5;\ 8;\ 11;\ 14;\ \ldots$",
                "steps": [
                    "It goes up by $3$ each time, so $T_n = 3n + c$",
                    "$T_1 = 5$: $3(1) + c = 5$, so $c = 2$",
                    "$T_n = 3n + 2$",
                ],
                "a": "$T_{50} = 3(50) + 2 = 152$",
                "say": {
                    "q": "Find the general term, and the fiftieth term, of five, eight, eleven, fourteen, and so on.",
                    "steps": [
                        "It goes up by three each time, so T n equals three n, plus c.",
                        "The first term is five, so three plus c equals five, and c is two.",
                        "So T n equals three n, plus two.",
                    ],
                    "a": "The fiftieth term is three times fifty, plus two. That's one hundred and fifty-two.",
                },
            },
        ],
    },
    "Trigonometry": {
        "what": "The ratios between the sides of a right-angled triangle: sine, cosine and tangent. You use them to find unknown sides and angles.",
        "visual": r"\sin\theta = \frac{\text{opp}}{\text{hyp}} \quad \cos\theta = \frac{\text{adj}}{\text{hyp}} \quad \tan\theta = \frac{\text{opp}}{\text{adj}}",
        "why": "It lets you measure things you can't reach, from one distance and one angle.",
        "expect": [
            "Sine, cosine and tangent in a right-angled triangle",
            "Their reciprocals: cosec, sec and cot",
            "Special angles: 30°, 45° and 60°, without a calculator",
            "Solving simple trig equations",
            "Graphs of sine, cosine and tangent",
            "Heights and distances in 2D problems",
        ],
        "previous": [
            "Grade 9 Theorem of Pythagoras",
            "Grade 9 Similar triangles",
        ],
        "paper": "Paper 2",
        "examples": [
            {
                "q": r"A right-angled triangle has sides $3$, $4$ and hypotenuse $5$. For the angle $\theta$ opposite the side $3$, find $\sin\theta$, $\cos\theta$ and $\tan\theta$.",
                "steps": [
                    r"$\sin\theta = \dfrac{\text{opp}}{\text{hyp}} = \dfrac{3}{5}$",
                    r"$\cos\theta = \dfrac{\text{adj}}{\text{hyp}} = \dfrac{4}{5}$",
                    r"$\tan\theta = \dfrac{\text{opp}}{\text{adj}} = \dfrac{3}{4}$",
                ],
                "a": r"$\sin\theta = \tfrac{3}{5}$, $\cos\theta = \tfrac{4}{5}$, $\tan\theta = \tfrac{3}{4}$",
                "say": {
                    "q": "A right-angled triangle has sides three and four, and a hypotenuse of five. For the angle theta opposite the side of three, find sine, cosine and tangent of theta.",
                    "steps": [
                        "Sine is opposite over hypotenuse: three over five.",
                        "Cosine is adjacent over hypotenuse: four over five.",
                        "Tangent is opposite over adjacent: three over four.",
                    ],
                    "a": "So sine theta is three fifths, cosine theta is four fifths, and tangent theta is three quarters.",
                },
            },
            {
                "q": r"A $5$ m ladder leans against a wall at $60^\circ$ to the ground. How high up the wall does it reach?",
                "steps": [
                    r"The ladder is the hypotenuse; the height is opposite the $60^\circ$ angle",
                    r"$\sin 60^\circ = \dfrac{h}{5}$, so $h = 5 \sin 60^\circ$",
                ],
                "a": r"$h \approx 4{,}33$ m",
                "say": {
                    "q": "A five metre ladder leans against a wall, at sixty degrees to the ground. How high up the wall does it reach?",
                    "steps": [
                        "The ladder is the hypotenuse, and the height is opposite the sixty degree angle.",
                        "So sine sixty degrees equals h over five, which means h equals five, times sine sixty degrees.",
                    ],
                    "a": "h is about four comma three three metres.",
                },
            },
        ],
    },
    "Functions": {
        "what": "A function is a rule that gives exactly one output for each input. In Grade 10: straight lines, parabolas, hyperbolas and exponential graphs.",
        "visual": r"y = ax + q \quad y = ax^2 + q \quad y = \frac{a}{x} + q \quad y = ab^x + q",
        "why": "Functions describe how one thing changes with another, and graphs let you see it.",
        "expect": [
            "What a function is: input, output, domain and range",
            "Straight-line graphs",
            "Parabolas",
            "Hyperbolas",
            "Exponential graphs",
            "How the values of a and q move and stretch a graph",
        ],
        "previous": [
            "Grade 9 Functions and relationships",
            "Grade 9 Graphs: drawing and reading straight-line graphs",
        ],
        "paper": "Paper 1",
        "examples": [
            {
                "q": "For $y = 2x + 1$, find $y$ when $x = 3$, and the $y$-intercept.",
                "steps": [
                    "Substitute $x = 3$: $y = 2(3) + 1 = 7$",
                    "The $y$-intercept is where $x = 0$: $y = 1$",
                ],
                "a": r"$y = 7$; the graph cuts the $y$-axis at $(0;\,1)$",
                "say": {
                    "q": "For y equals two x plus one, find y when x is three, and the y-intercept.",
                    "steps": [
                        "Substitute x equals three: two times three, plus one, is seven.",
                        "The y-intercept is where x is zero, so y is one.",
                    ],
                    "a": "y is seven, and the graph cuts the y-axis at zero, one.",
                },
            },
            {
                "q": "Sketch the key points of $y = x^2 - 4$",
                "steps": [
                    "$y$-intercept: put $x = 0$, so $y = -4$",
                    r"$x$-intercepts: $x^2 - 4 = 0$, so $x = \pm 2$",
                    r"$a > 0$, so it opens upward with turning point $(0;\,-4)$",
                ],
                "a": r"A ∪-shaped parabola through $(-2;\,0)$, $(0;\,-4)$ and $(2;\,0)$",
                "say": {
                    "q": "Find the key points of y equals x squared, minus four.",
                    "steps": [
                        "The y-intercept: put x equal to zero, and y is negative four.",
                        "The x-intercepts: x squared minus four equals zero, so x is plus or minus two.",
                        "a is positive, so the graph opens upward, with its turning point at zero, negative four.",
                    ],
                    "a": "A U-shaped parabola, through negative two, zero; zero, negative four; and two, zero.",
                },
            },
        ],
    },
    "Finance, Growth and Decay": {
        "what": "How money grows or shrinks over time: simple and compound interest, hire purchase, inflation and exchange rates.",
        "visual": r"A = P(1 + in) \qquad A = P(1 + i)^n",
        "why": "Every adult borrows, saves and pays prices that rise. This topic shows you what that really costs.",
        "expect": [
            "Simple interest",
            "Compound interest",
            "Hire purchase",
            "Inflation and population growth",
            "Foreign exchange rates",
        ],
        "previous": [
            "Grade 9 Financial mathematics: interest, hire purchase and exchange rates",
            "Percentages",
        ],
        "paper": "Paper 1",
        "examples": [
            {
                "q": r"R2 000 is invested at $10\%$ simple interest per year for $3$ years. How much is it worth?",
                "steps": [
                    r"$A = P(1 + in)$ with $P = 2\,000$, $i = 0{,}1$, $n = 3$",
                    r"$A = 2\,000(1 + 0{,}3) = 2\,000(1{,}3)$",
                ],
                "a": r"$A = \text{R}2\,600$",
                "say": {
                    "q": "Two thousand rand is invested at ten percent simple interest per year, for three years. How much is it worth?",
                    "steps": [
                        "Use A equals P, times one plus i n. P is two thousand, i is zero comma one, and n is three.",
                        "So A equals two thousand, times one comma three.",
                    ],
                    "a": "That's two thousand, six hundred rand.",
                },
            },
            {
                "q": r"R5 000 is invested at $8\%$ per year, compound interest, for $3$ years. What is it worth?",
                "steps": [
                    r"$A = P(1 + i)^n$ with $P = 5\,000$, $i = 0{,}08$, $n = 3$",
                    r"$A = 5\,000(1{,}08)^3$",
                ],
                "a": r"$A = \text{R}6\,298{,}56$ (simple interest would give R6 200)",
                "say": {
                    "q": "Five thousand rand is invested at eight percent per year, compound interest, for three years. What is it worth?",
                    "steps": [
                        "Use A equals P, times one plus i, to the power n. P is five thousand, i is zero comma zero eight, and n is three.",
                        "So A equals five thousand, times one comma zero eight, cubed.",
                    ],
                    "a": "That's six thousand, two hundred and ninety-eight rand, fifty-six. Simple interest would give only six thousand, two hundred rand.",
                },
            },
        ],
    },
    "Analytical Geometry": {
        "what": "Geometry on the Cartesian plane. You use coordinates to find distances, midpoints and gradients.",
        "visual": r"d = \sqrt{(x_2 - x_1)^2 + (y_2 - y_1)^2}",
        "why": "It turns shapes into numbers, so a computer or a calculator can work with them.",
        "expect": [
            "The distance between two points",
            "The midpoint of a line segment",
            "The gradient of a line",
            "Parallel and perpendicular lines",
            "Using these to prove what shape a figure is",
        ],
        "previous": [
            "Grade 9 The Cartesian plane: plotting points",
            "Grade 9 Theorem of Pythagoras",
        ],
        "paper": "Paper 2",
        "examples": [
            {
                "q": r"Find the midpoint of $P(2;\,4)$ and $Q(8;\,10)$.",
                "steps": [
                    r"Average the $x$-values: $\dfrac{2 + 8}{2} = 5$",
                    r"Average the $y$-values: $\dfrac{4 + 10}{2} = 7$",
                ],
                "a": r"Midpoint $= (5;\,7)$",
                "say": {
                    "q": "Find the midpoint of P, two, four, and Q, eight, ten.",
                    "steps": [
                        "Average the x-values: two plus eight, over two, is five.",
                        "Average the y-values: four plus ten, over two, is seven.",
                    ],
                    "a": "The midpoint is five, seven.",
                },
            },
            {
                "q": r"$A(1;\,2)$ and $B(7;\,10)$. Find $AB$, the midpoint and the gradient.",
                "steps": [
                    r"$AB = \sqrt{6^2 + 8^2} = \sqrt{100} = 10$",
                    r"Midpoint $= \left(\dfrac{1+7}{2};\ \dfrac{2+10}{2}\right) = (4;\,6)$",
                    r"Gradient $= \dfrac{10 - 2}{7 - 1} = \dfrac{8}{6} = \dfrac{4}{3}$",
                ],
                "a": r"$AB = 10$, midpoint $(4;\,6)$, gradient $\tfrac{4}{3}$",
                "say": {
                    "q": "A is the point one, two, and B is seven, ten. Find the length A B, the midpoint, and the gradient.",
                    "steps": [
                        "A B is the square root of six squared plus eight squared. That's the square root of a hundred, which is ten.",
                        "The midpoint is the average of the coordinates: four, six.",
                        "The gradient is the change in y over the change in x: eight over six, which is four thirds.",
                    ],
                    "a": "So A B is ten, the midpoint is four, six, and the gradient is four thirds.",
                },
            },
        ],
    },
    "Euclidean Geometry": {
        "what": "The properties of lines, triangles and quadrilaterals, and proving them step by step with a reason for each statement.",
        "visual": r"\text{Statement} \;\;|\;\; \text{Reason}",
        "why": "It trains you to argue logically: every claim needs a reason.",
        "expect": [
            "Revision: lines, angles and triangles",
            "Properties of the parallelogram, rectangle, rhombus, square, kite and trapezium",
            "The midpoint theorem",
            "Writing proofs, with a reason for every statement",
        ],
        "previous": [
            "Grade 9 Geometry of straight lines: angles and parallel lines",
            "Grade 9 Geometry of 2D shapes: triangles, quadrilaterals, congruence and similarity",
        ],
        "paper": "Paper 2",
        "examples": [
            {
                "q": r"Two angles of a triangle are $50^\circ$ and $60^\circ$. Find the third angle.",
                "steps": [
                    r"The angles of a triangle add up to $180^\circ$",
                    r"$180^\circ - 50^\circ - 60^\circ = 70^\circ$",
                ],
                "a": r"$70^\circ$  (reason: sum of the angles of a triangle)",
                "say": {
                    "q": "Two angles of a triangle are fifty degrees and sixty degrees. Find the third angle.",
                    "steps": [
                        "The angles of a triangle add up to one hundred and eighty degrees.",
                        "One hundred and eighty, minus fifty, minus sixty, is seventy.",
                    ],
                    "a": "The third angle is seventy degrees. Reason: the sum of the angles of a triangle.",
                },
            },
            {
                "q": r"In $\triangle ABC$, $D$ and $E$ are the midpoints of $AB$ and $AC$. $BC = 12$ cm. Find $DE$.",
                "steps": [
                    "$D$ and $E$ are midpoints of two sides of the triangle",
                    r"Midpoint theorem: $DE \parallel BC$ and $DE = \tfrac{1}{2}BC$",
                ],
                "a": "$DE = 6$ cm  (reason: midpoint theorem)",
                "say": {
                    "q": "In triangle A B C, D and E are the midpoints of A B and A C. B C is twelve centimetres. Find D E.",
                    "steps": [
                        "D and E are the midpoints of two sides of the triangle.",
                        "The midpoint theorem says D E is parallel to B C, and half as long.",
                    ],
                    "a": "So D E is six centimetres. Reason: the midpoint theorem.",
                },
            },
        ],
    },
    "Measurement": {
        "what": "Surface area and volume of 3D shapes: prisms, cylinders, pyramids, cones and spheres.",
        "visual": r"V_{\text{cylinder}} = \pi r^2 h",
        "why": "It tells you how much something holds, and how much material it takes to make or cover it.",
        "expect": [
            "Surface area of prisms, cylinders, pyramids, cones and spheres",
            "Volume of the same shapes",
            "What happens when you multiply a length by a factor",
            "Converting units, including to litres",
        ],
        "previous": [
            "Grade 9 Area and perimeter of 2D shapes",
            "Grade 9 Surface area and volume of prisms and cylinders",
        ],
        "paper": "Paper 2",
        "examples": [
            {
                "q": "Find the volume of a box $4$ cm long, $3$ cm wide and $2$ cm high.",
                "steps": [
                    r"Volume of a rectangular prism $=$ length $\times$ breadth $\times$ height",
                    r"$4 \times 3 \times 2 = 24$",
                ],
                "a": "$24$ cm³",
                "say": {
                    "q": "Find the volume of a box four centimetres long, three centimetres wide and two centimetres high.",
                    "steps": [
                        "The volume of a rectangular prism is length, times breadth, times height.",
                        "Four times three times two is twenty-four.",
                    ],
                    "a": "The volume is twenty-four cubic centimetres.",
                },
            },
            {
                "q": "A cylindrical tank has radius $0{,}5$ m and height $2$ m. How much water does it hold?",
                "steps": [
                    r"$V = \pi r^2 h = \pi (0{,}5)^2 (2)$",
                    r"$V \approx 1{,}57$ m³, and $1$ m³ $= 1\,000$ litres",
                ],
                "a": r"About $1\,570$ litres",
                "say": {
                    "q": "A cylindrical tank has a radius of zero comma five metres, and a height of two metres. How much water does it hold?",
                    "steps": [
                        "Volume equals pi r squared h: pi, times zero comma five squared, times two.",
                        "That's about one comma five seven cubic metres. And one cubic metre holds a thousand litres.",
                    ],
                    "a": "So it holds about one thousand, five hundred and seventy litres.",
                },
            },
        ],
    },
    "Statistics": {
        "what": "Collecting, organising and summarising data: mean, median, mode, range, quartiles and box-and-whisker plots.",
        "visual": r"\bar{x} = \frac{\text{sum of values}}{\text{number of values}}",
        "why": "Data is everywhere. Statistics helps you see the story in it and spot claims that don't add up.",
        "expect": [
            "Mean, median and mode",
            "Range, quartiles and the interquartile range",
            "The five-number summary and box-and-whisker plots",
            "Grouped data: estimating the mean, and the modal class",
        ],
        "previous": [
            "Grade 9 Data handling: collecting, organising and summarising data",
            "Grade 9 Mean, median, mode and range",
        ],
        "paper": "Paper 2",
        "examples": [
            {
                "q": r"Find the mode of $6;\ 2;\ 6;\ 8;\ 3$.",
                "steps": [
                    r"Put the data in order: $2;\ 3;\ 6;\ 6;\ 8$",
                    "The mode is the value that appears most often",
                ],
                "a": "Mode $= 6$",
                "say": {
                    "q": "Find the mode of six, two, six, eight and three.",
                    "steps": [
                        "Put the data in order: two, three, six, six, eight.",
                        "The mode is the value that appears most often.",
                    ],
                    "a": "The mode is six.",
                },
            },
            {
                "q": r"Find the mean, median and range of $3;\ 5;\ 7;\ 8;\ 12$",
                "steps": [
                    r"Mean $= \dfrac{3 + 5 + 7 + 8 + 12}{5} = \dfrac{35}{5} = 7$",
                    "Median: the middle value of the ordered list is $7$",
                    "Range $= 12 - 3 = 9$",
                ],
                "a": "Mean $7$, median $7$, range $9$",
                "say": {
                    "q": "Find the mean, median and range of three, five, seven, eight and twelve.",
                    "steps": [
                        "The mean: add them to get thirty-five, and divide by five. That's seven.",
                        "The median: the middle value of the ordered list is seven.",
                        "The range: twelve minus three is nine.",
                    ],
                    "a": "Mean seven, median seven, range nine.",
                },
            },
        ],
    },
    "Probability": {
        "what": "How likely something is to happen, from 0 (impossible) to 1 (certain), using sample spaces and Venn diagrams.",
        "visual": r"P(E) = \frac{\text{number of favourable outcomes}}{\text{total number of outcomes}}",
        "why": "It helps you make decisions when you can't be sure of the result.",
        "expect": [
            "Probability from 0 (impossible) to 1 (certain)",
            "Relative frequency from experiments",
            "Sample spaces and Venn diagrams",
            "Mutually exclusive and complementary events",
            "The addition rule for 'or' events",
        ],
        "previous": [
            "Grade 9 Probability: outcomes and relative frequency",
            "Grade 9 Tree diagrams and two-way tables",
        ],
        "paper": "Paper 1",
        "examples": [
            {
                "q": r"A fair die is rolled once. Find $P(4)$ and $P(\text{even number})$.",
                "steps": [
                    r"There are $6$ equally likely outcomes, and one of them is a $4$: $P(4) = \dfrac{1}{6}$",
                    "The even numbers are $2$, $4$ and $6$: three of the six outcomes",
                ],
                "a": r"$P(4) = \tfrac{1}{6}$, $P(\text{even}) = \tfrac{3}{6} = \tfrac{1}{2}$",
                "say": {
                    "q": "A fair die is rolled once. Find the probability of a four, and of an even number.",
                    "steps": [
                        "There are six equally likely outcomes, and one of them is a four, so the probability is one sixth.",
                        "The even numbers are two, four and six: three of the six outcomes.",
                    ],
                    "a": "So the probability of a four is one sixth, and of an even number, three sixths, which is a half.",
                },
            },
            {
                "q": r"A bag has $3$ red and $5$ blue marbles. Find $P(\text{red})$ and $P(\text{not red})$.",
                "steps": [
                    r"There are $8$ marbles, and $3$ are red: $P(\text{red}) = \dfrac{3}{8}$",
                    r"Not red is the complement: $P(\text{not red}) = 1 - \dfrac{3}{8}$",
                ],
                "a": r"$P(\text{red}) = \tfrac{3}{8}$, $P(\text{not red}) = \tfrac{5}{8}$",
                "say": {
                    "q": "A bag has three red and five blue marbles. Find the probability of red, and of not red.",
                    "steps": [
                        "There are eight marbles, and three are red, so the probability of red is three eighths.",
                        "Not red is the complement: one minus three eighths.",
                    ],
                    "a": "So the probability of red is three eighths, and of not red, five eighths.",
                },
            },
        ],
    },
}

# (subject name in the seed, grade) -> content
CONTENT = {
    ("Pure Mathematics", 10): GRADE10_MATHS,
}
