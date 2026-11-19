"""deep scan H4: security headers and frontend crash reports."""


async def test_security_headers_on_every_response(client):
    r = await client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


async def test_client_error_reports_are_limited(client):
    body = {"message": "TypeError: x is undefined", "stack": "at Foo", "path": "/"}
    codes = [(await client.post("/client-errors", json=body)).status_code for _ in range(25)]
    assert set(codes) == {204}  # over the limit is dropped quietly, never an error
    assert (await client.post("/client-errors", json={"message": "x" * 600})).status_code == 422


async def test_large_responses_are_compressed(client, world):
    """deep scan M6."""
    r = await client.get("/api/v1/dashboard/progress", headers={**world.h("teacher_a"), "Accept-Encoding": "gzip"})
    assert r.status_code == 200
    if len(r.content) >= 1024:
        assert r.headers.get("content-encoding") == "gzip"
    r = await client.get("/topics/", headers={**world.h("teacher_a"), "Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip"
