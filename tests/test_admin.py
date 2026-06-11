from app.core.auth import CurrentUser


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _user(verifier, token="tok-a", uid="user-a", name="Ada") -> str:
    verifier.add(token, CurrentUser(uid=uid, email=f"{uid}@x.com", display_name=name))
    return token


def test_signed_in_user_can_read_dashboard_metrics(client, verifier, repo):
    token = _user(verifier)
    repo.set(
        "trips",
        "trip-1",
        {
            "name": "Lisbon Long Weekend",
            "destination": {"text": "Lisbon", "lat": 38.7, "lng": -9.1},
            "startDate": "2026-07-10",
            "endDate": "2026-07-13",
            "adminUid": "user-a",
            "createdAt": "2026-06-01T00:00:00+00:00",
        },
    )
    repo.set(
        "trips/trip-1/generations",
        "gen-1",
        {
            "status": "complete",
            "startedAt": "2026-06-10T12:00:00+00:00",
            "traceId": "a" * 32,
            "metrics": {
                "latencyMs": 125000,
                "totalTokens": 5000,
                "tokensPerSecond": 40.0,
                "estCostUsd": 0.004,
                "billingTier": "free",
            },
        },
    )
    repo.set(
        "whims",
        "whim-1",
        {
            "whimText": "something sweet near me",
            "createdAt": "2026-06-10T12:05:00+00:00",
            "traceId": "b" * 32,
            "metrics": {
                "latencyMs": 900,
                "totalTokens": 120,
                "tokensPerSecond": 133.33,
                "estCostUsd": 0.00008,
                "billingTier": "free",
            },
        },
    )
    repo.set(
        "evalRuns",
        "eval-1",
        {
            "timestamp": "2026-06-10T12:10:00+00:00",
            "model": "gemini-3.1-flash-lite",
            "gitSha": "abc123",
            "aggregates": {
                "schemaValidity": 1.0,
                "groundedness": 0.9,
                "constraintAdherence": 1.0,
                "suggestedFlagHonesty": 1.0,
            },
        },
    )

    generations = client.get("/admin/generations/recent", headers=_auth(token))
    whims = client.get("/admin/whims/recent", headers=_auth(token))
    eval_runs = client.get("/admin/eval-runs", headers=_auth(token))

    assert generations.status_code == 200
    assert generations.json() == [
        {
            "tripId": "trip-1",
            "tripName": "Lisbon Long Weekend",
            "status": "complete",
            "latencyMs": 125000,
            "totalTokens": 5000,
            "tokensPerSecond": 40.0,
            "estCostUsd": 0.004,
            "billingTier": "free",
            "traceId": "a" * 32,
            "startedAt": "2026-06-10T12:00:00+00:00",
        }
    ]
    assert whims.status_code == 200
    assert whims.json() == [
        {
            "whimId": "whim-1",
            "whimText": "something sweet near me",
            "latencyMs": 900,
            "totalTokens": 120,
            "tokensPerSecond": 133.33,
            "estCostUsd": 0.00008,
            "billingTier": "free",
            "traceId": "b" * 32,
            "createdAt": "2026-06-10T12:05:00+00:00",
        }
    ]
    assert eval_runs.status_code == 200
    assert eval_runs.json() == [
        {
            "runId": "eval-1",
            "timestamp": "2026-06-10T12:10:00+00:00",
            "model": "gemini-3.1-flash-lite",
            "gitSha": "abc123",
            "aggregates": {
                "schemaValidity": 1.0,
                "groundedness": 0.9,
                "constraintAdherence": 1.0,
                "suggestedFlagHonesty": 1.0,
            },
        }
    ]


def test_admin_metrics_require_auth(client):
    response = client.get("/admin/generations/recent")

    assert response.status_code == 401
