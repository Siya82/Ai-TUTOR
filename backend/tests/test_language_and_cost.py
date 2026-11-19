"""ADR-035: home-language bridging and AI cost settings."""

from app.services.personalization import HOME_LANGUAGES, build_language_instructions


def test_no_language_block_for_english_or_unset():
    assert build_language_instructions(None) == ""
    assert build_language_instructions("English") == ""


def test_unknown_language_is_ignored():
    assert build_language_instructions("Klingon") == ""


def test_home_language_block_keeps_english_exam_terms():
    text = build_language_instructions("isiZulu")
    assert "isiZulu" in text
    assert "English" in text
    assert "formulas" in text


def test_all_eleven_official_languages_offered():
    assert len(HOME_LANGUAGES) == 11
    assert HOME_LANGUAGES[0] == "English"
