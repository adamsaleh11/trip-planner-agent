import json

from app.core.auth import CurrentUser


def _access_line(captured: str) -> dict:
    records = [
        json.loads(ln)
        for ln in captured.splitlines()
        if ln.strip().startswith("{")
    ]
    access = [r for r in records if r.get("logger") == "app.access"]
    assert access, f"no access log line found in: {captured!r}"
    return access[-1]


def test_authenticated_request_logs_structured_line(client, verifier, capsys):
    verifier.add("good", CurrentUser(uid="u1", email="a@b.com"))

    client.get("/me", headers={"Authorization": "Bearer good"})

    record = _access_line(capsys.readouterr().out)
    assert record["request_id"]
    assert record["uid"] == "u1"
    assert record["path"] == "/me"
    assert record["method"] == "GET"
    assert record["status"] == 200
    assert isinstance(record["latency_ms"], (int, float))


def test_unauthenticated_request_logs_anon_uid(client, capsys):
    client.get("/healthz")

    record = _access_line(capsys.readouterr().out)
    assert record["uid"] == "anon"
    assert record["path"] == "/healthz"
    assert record["status"] == 200


def test_service_logs_carry_request_id(client, verifier, capsys):
    verifier.add("good", CurrentUser(uid="u1", email="a@b.com"))

    client.get("/me", headers={"Authorization": "Bearer good"})

    out = capsys.readouterr().out
    provision_lines = [
        json.loads(ln)
        for ln in out.splitlines()
        if ln.strip().startswith("{") and "provisioned user profile" in ln
    ]
    assert provision_lines, "expected a service log line for provisioning"
    assert provision_lines[0]["request_id"]
