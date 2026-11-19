"""code review 19 Nov #15: the extra questions fit real topics, and the
numeric answers are right (re-computed here, independently)."""

import math

from scripts import seed_dev_data as seed
from scripts.question_bank_extra import EXTRA_QUESTIONS


def test_every_extra_topic_exists_and_questions_are_new():
    specs = {(s["name"], s["grade"]): s for s in seed.SUBJECTS}
    for key, by_topic in EXTRA_QUESTIONS.items():
        spec = specs[key]
        topic_names = {t for t, _ in spec["topics"]}
        for topic, pairs in by_topic.items():
            assert topic in topic_names, (key, topic)
            existing = {q for q, _ in spec["questions"].get(topic, [])}
            for q, a in pairs:
                assert q not in existing and q.strip() and a.strip(), (key, topic, q)


def test_numeric_answers():
    fv = 500 * ((1.01**24 - 1) / 0.01)
    assert f"{fv:,.2f}".replace(",", " ") == "13 486.73"
    pv = 1000 * ((1 - 1.01**-12) / 0.01)
    assert round(pv, 2) == 11255.08
    assert round(math.log(2) / math.log(1.08), 2) == 9.01
    assert round(math.log(20) / math.log(5), 2) == 1.86
    assert round((1.01**12 - 1) * 100, 2) == 12.68
    assert round(10 * math.sin(math.radians(45)) / math.sin(math.radians(30)), 2) == 14.14
    assert round(math.sqrt(5**2 + 7**2 - 2 * 5 * 7 * math.cos(math.radians(60))), 2) == 6.24
    assert round(0.5 * 6 * 8 * math.sin(math.radians(30)), 6) == 12
    assert 20 / 2 * (2 * 3 + 19 * 4) == 820 and 2 * 3**5 == 486 and 8 / (1 - 0.5) == 16
    assert round(2000 * 1.1**3, 2) == 2662
    assert round(50000 * 0.8**2, 2) == 32000
    assert round(1.4641 ** 0.25, 6) == 1.1
    # physics
    assert round(6.63e-34 * 5e14 * 1e19, 3) == 3.315  # quoted as 3.32 x 10^-19 J
    assert round(2e-9 / 1.6e-19 / 1e10, 2) == 1.25
    assert round(6.67e-11 * 1000 * 1000 / 2**2 * 1e5, 2) == 1.67
    assert round(9e9 * 2e-6 * 3e-6 / 0.3**2, 6) == 0.6
    assert round(9e9 * 4e-6 / 0.2**2) == 900000
    assert round(340 / (340 - 20) * 500, 2) == 531.25
    assert round(340 / math.sqrt(2), 2) == 240.42
    assert round(3.2e-19 / 6.63e-34 / 1e14, 2) == 4.83
    assert round(20 * math.cos(math.radians(30)), 2) == 17.32
    assert round(19.6**2 / (2 * 9.8), 6) == 19.6 and 19.6 / 9.8 == 2
    assert round(math.degrees(math.atan(4 / 3)), 2) == 53.13
    assert 2 * 9.8 * 5 == 98 and 0.5 * 4 * 3**2 == 18 and 60 * 9.8 == 588


def test_algebra_answers():
    import sympy as sp

    x = sp.symbols("x")
    assert sp.factor(x**3 - 6 * x**2 + 11 * x - 6) == (x - 1) * (x - 2) * (x - 3)
    assert (x**3 - 2 * x + 1).subs(x, 2) == 5
    assert sp.solve((x**3 + sp.Symbol("k") * x + 3).subs(x, -1), sp.Symbol("k")) == [2]
    assert sp.diff(x**3 - 3 * x, x).subs(x, 1) == 0
    assert set(sp.solve(x**2 + 2 * x - 4, x)) == {-1 + sp.sqrt(5), -1 - sp.sqrt(5)}
    assert sp.simplify((2 * x**2 - 8) / (x - 2)) == 2 * x + 4
    n = sp.symbols("n")
    assert [(n**2 + n).subs(n, i) for i in range(1, 5)] == [2, 6, 12, 20]
