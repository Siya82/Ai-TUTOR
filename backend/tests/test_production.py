"""deep scan H4: unsafe production settings stop the API from starting."""

from types import SimpleNamespace

import pytest

from app.core.production import UnsafeProductionSettings, check_production_settings, problems

GOOD = dict(environment="production", jwt_secret_key="k" * 48, cors_origins=["https://app.thutora.co.za"],
            sms_provider="", anthropic_api_key="sk-ant-real")


def s(**over):
    return SimpleNamespace(**{**GOOD, **over})


def test_good_production_settings_pass():
    assert problems(s()) == []


@pytest.mark.parametrize("over, text", [
    (dict(jwt_secret_key="short"), "JWT_SECRET_KEY"),
    (dict(cors_origins=["http://localhost:5173"]), "localhost"),
    (dict(cors_origins=["http://app.thutora.co.za"]), "https"),
    (dict(sms_provider="console"), "SMS_PROVIDER"),
    (dict(anthropic_api_key=""), "ANTHROPIC_API_KEY"),
])
def test_each_unsafe_setting_is_caught(over, text):
    with pytest.raises(UnsafeProductionSettings, match=text):
        check_production_settings(s(**over))


def test_development_is_not_checked():
    assert problems(s(environment="development", jwt_secret_key="x", sms_provider="console")) == []
