"""deep scan M5: spotting a test question pasted or retyped into the tutor."""

from app.services.test_integrity import matches_question

Q = "A geometric series has first term a = 8 and common ratio r = 1/2. Calculate the sum to infinity."


def test_pasted_question_matches():
    assert matches_question(Q, Q)
    assert matches_question("please help: " + Q, Q)


def test_retyped_with_small_changes_matches():
    assert matches_question("a geometric series has first term a=8 and common ratio r=1/2, calculate the sum to infinity", Q)


def test_general_questions_do_not_match():
    assert not matches_question("What is a geometric series?", Q)
    assert not matches_question("how do I find the sum to infinity in general", Q)
    assert not matches_question("help", Q)
