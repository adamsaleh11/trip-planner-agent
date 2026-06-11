from app.core.auth import CurrentUser
from app.core.observability import get_recorded_spans, reset_recorded_spans
from tests.test_generation import TRIP_PAYLOAD, ScriptedGenerationRunner
from tests.test_whims import ScriptedWhimRunner


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _user(verifier, token="tok-a", uid="user-a", name="Ada") -> str:
    verifier.add(token, CurrentUser(uid=uid, email=f"{uid}@x.com", display_name=name))
    return token


def test_whim_request_records_trace_without_whim_text_attribute(
    client, verifier
):
    from app.services.whims import get_whim_runner

    runner = ScriptedWhimRunner()
    client.app.dependency_overrides[get_whim_runner] = lambda: runner
    token = _user(verifier)
    reset_recorded_spans()

    response = client.post(
        "/whims",
        json={
            "whimText": "secret dessert craving",
            "location": {"city": "Lisbon"},
        },
        headers=_auth(token),
    )

    assert response.status_code == 200
    spans = get_recorded_spans()
    root = next(span for span in spans if span.name == "whim.request")
    assert root.trace_id
    assert all(
        "secret dessert craving" not in str(value)
        for span in spans
        for value in span.attributes.values()
    )


def test_trip_generation_records_generation_trace_without_preference_text(
    client, verifier, repo
):
    from app.services.generation import get_generation_runner

    runner = ScriptedGenerationRunner()
    client.app.dependency_overrides[get_generation_runner] = lambda: runner
    token = _user(verifier)
    trip_id = client.post("/trips", json=TRIP_PAYLOAD, headers=_auth(token)).json()["id"]
    participant_id = client.get(
        f"/trips/{trip_id}/participants",
        headers=_auth(token),
    ).json()[0]["id"]
    client.put(
        f"/trips/{trip_id}/preferences/participants/{participant_id}/food_drink",
        json={"freeText": "secret pastry preference", "cuisineInterests": ["seafood"]},
        headers=_auth(token),
    )
    reset_recorded_spans()

    response = client.post(f"/trips/{trip_id}/generate", headers=_auth(token))

    assert response.status_code == 202
    generation = repo.get(f"trips/{trip_id}/generations", response.json()["generationId"])
    root = next(span for span in get_recorded_spans() if span.name == "generation.request")
    assert root.trace_id == generation["traceId"]
    assert all(
        "secret pastry preference" not in str(value)
        for span in get_recorded_spans()
        for value in span.attributes.values()
    )
