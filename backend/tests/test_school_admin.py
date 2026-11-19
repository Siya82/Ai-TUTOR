"""ADR-044: the ADMIN overview's to-do list."""

from app.routers.school_admin import build_todos


def _o(**kw):
    o = {
        "learners": {"active": 10, "not_in_class": 0, "with_consent": 10},
        "classes": {"without_teacher": 0},
        "staff": {"without_work": 0},
        "families": {"with_contact": 10},
    }
    for path, v in kw.items():
        a, b = path.split("__")
        o[a][b] = v
    return o


def test_nothing_to_do():
    assert build_todos(_o()) == []


def test_singular_and_plural():
    todos = build_todos(_o(learners__not_in_class=1, classes__without_teacher=3))
    assert todos[0]["text"] == "1 learner isn't in a class yet"
    assert todos[1]["text"] == "3 classes have no teacher allocated"


def test_consent_and_contacts_count_from_active():
    todos = build_todos(_o(learners__with_consent=7, families__with_contact=9))
    texts = [t["text"] for t in todos]
    assert "3 learners have no consent recorded" in texts
    assert "1 learner has no guardian cellphone on record" in texts
    assert {t["tab"] for t in todos} == {"learners"}
