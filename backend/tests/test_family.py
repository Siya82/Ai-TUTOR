"""ADR-043: parent verification helpers and the CSV guardian columns."""

import pytest

from app.services.admin import parse_student_csv
from app.services.family import (
    invite_hash,
    local_format,
    new_invite_code,
    new_otp,
    normalize_sa_cellphone,
    otp_matches,
)


@pytest.mark.parametrize(
    "raw", ["082 123 4567", "0821234567", "+27 82 123 4567", "27821234567", "0027821234567", "082-123-4567"]
)
def test_sa_cellphones_normalise(raw):
    assert normalize_sa_cellphone(raw) == "+27821234567"


@pytest.mark.parametrize("raw", ["", "12345", "011 123 4567", "+44 7700 900123", "082 123 456"])
def test_non_cellphones_rejected(raw):
    with pytest.raises(ValueError):
        normalize_sa_cellphone(raw)


def test_local_format():
    assert local_format("+27821234567") == "0821234567"


def test_otp_round_trip():
    code, h = new_otp()
    assert len(code) == 6 and code.isdigit()
    assert otp_matches(code, h)
    assert not otp_matches("000000" if code != "000000" else "111111", h)


def test_invite_codes_tolerate_dashes_and_case():
    code, h = new_invite_code()
    assert invite_hash(code) == h
    assert invite_hash(code.replace("-", "").lower()) == h


def test_csv_guardian_columns():
    csv = (
        "display_name,grade,guardian_name,guardian_relationship,guardian_cellphone\n"
        "Ayanda Dlamini,10,Thandi Dlamini,Mother,082 555 1234\n"
        "Bongani Zulu,11,,,\n"
        "Chloe Naidoo,12,,,0825551234\n"
        "Dumi Khumalo,10,Mr Khumalo,Father,12345\n"
    )
    out = parse_student_csv(csv)
    assert [r.display_name for r in out.rows] == ["Ayanda Dlamini", "Bongani Zulu"]
    assert out.rows[0].guardian_cellphone == "+27825551234"
    assert out.rows[1].guardian_name is None
    assert [e[0] for e in out.errors] == [4, 5]
