"""deep scan M2, M3, M4, L6: abuse paths, counted in the database."""

from tests.integration.conftest import PASSWORD


async def _login(client, world, who, password, device):
    return await client.post(
        "/auth/login",
        headers={"X-Device-Id": device},
        json={"school_id": str(world.school.id), "student_number": world.users[who].student_number,
              "password": password},
    )


async def test_classmate_cannot_lock_someone_out(client, world):
    for _ in range(5):  # a classmate on their own phone
        assert (await _login(client, world, "a1", "wrong-guess", "classmate-phone")).status_code == 401
    blocked = await _login(client, world, "a1", "wrong-guess", "classmate-phone")
    assert blocked.status_code == 429 and "this device" in blocked.json()["detail"]
    # ...but the real learner on their own device logs in fine
    assert (await _login(client, world, "a1", PASSWORD, "learner-laptop")).status_code == 200


async def test_many_devices_still_lock_the_login(client, world):
    for i in range(30):
        await _login(client, world, "a2", "wrong", f"device-{i}")
    r = await _login(client, world, "a2", PASSWORD, "fresh-device")
    assert r.status_code == 429


async def test_invite_redeem_is_rate_limited(client, world):
    codes = []
    for i in range(12):
        r = await client.post("/connect/viewer/redeem",
                              json={"school_id": str(world.school.id), "code": f"ABCD-{i:04d}", "password": "Secret123!"})
        codes.append(r.status_code)
    assert codes[:10] == [400] * 10 and 429 in codes[10:]


async def test_uploads_check_content_size_and_quota(client, world, monkeypatch):
    from app.core.config import settings

    h = world.h("a1")
    fake_pdf = ("worksheet.pdf", b"<html><script>alert(1)</script></html>", "application/pdf")
    r = await client.post("/attachments/", headers=h, files={"file": fake_pdf})
    assert r.status_code == 415  # says PDF, isn't one

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    ok = await client.post("/attachments/", headers=h, files={"file": ("work.png", png, "image/png")})
    assert ok.status_code == 200, ok.text

    monkeypatch.setattr(settings, "upload_daily_limit", 1)
    again = await client.post("/attachments/", headers=h, files={"file": ("work2.png", png, "image/png")})
    assert again.status_code == 429
