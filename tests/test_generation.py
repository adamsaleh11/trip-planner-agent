from datetime import datetime, timezone
from types import SimpleNamespace

from app.core.auth import CurrentUser


TRIP_PAYLOAD = {
    "name": "Lisbon Long Weekend",
    "destination": {
        "text": "Lisbon, Portugal",
        "lat": 38.7223,
        "lng": -9.1393,
        "placeId": "places/lisbon",
    },
    "startDate": "2026-07-10",
    "endDate": "2026-07-13",
    "lodgingArea": "Alfama",
}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _user(verifier, token="tok-a", uid="user-a", name="Ada") -> str:
    verifier.add(token, CurrentUser(uid=uid, email=f"{uid}@x.com", display_name=name))
    return token


def _create_trip(client, token: str) -> str:
    return client.post("/trips", json=TRIP_PAYLOAD, headers=_auth(token)).json()["id"]


class ScriptedGenerationRunner:
    def __init__(self) -> None:
        self.category_calls = []
        self.coordinator_calls = []
        self.fallback_calls = []
        self.fail_categories = set()
        self.candidate_overrides = {}

    def run_category(self, *, category, trip, group_preferences, trace_id):
        self.category_calls.append(
            {
                "category": category,
                "participantIds": [entry.participantId for entry in group_preferences],
            }
        )
        if category in self.fail_categories:
            raise RuntimeError(f"{category} failed")
        return {
            "candidates": [
                {
                    "name": "Cafe Lisboa",
                    "place_id": "places/cafe-lisboa",
                    "address": "Rua A, Lisbon",
                    "lat": 38.71,
                    "lng": -9.14,
                    "why_it_fits": "Matches the group's coffee preference.",
                    "time_of_day_fit": "morning",
                    "estimated_price_level": "$$",
                    "suggested": False,
                    "travelers_tip": "Travelers tip: order the pastry before noon.",
                    **self.candidate_overrides,
                }
            ],
            "metrics": {
                "totalTokens": 10,
                "promptTokens": 6,
                "outputTokens": 4,
                "latencyMs": 25,
                "estCostUsd": 0.00001,
                "llmCalls": 1,
                "toolCalls": 1,
                "tokensPerSecond": 400.0,
                "billingTier": "free",
            },
            "toolResults": [{"places": [{"id": "places/cafe-lisboa"}]}],
        }

    def run_category_fallback(
        self, *, category, trip, group_preferences, trace_id, reason
    ):
        self.fallback_calls.append({"category": category, "reason": reason})
        return {
            "candidates": [
                {
                    "name": "Generic Lisbon Pick",
                    "place_id": "places/cafe-lisboa",
                    "address": "Rua A, Lisbon",
                    "lat": 38.71,
                    "lng": -9.14,
                    "why_it_fits": "A safe default for this destination.",
                    "time_of_day_fit": "flexible",
                    "estimated_price_level": "Not available",
                    "suggested": True,
                }
            ],
            "metrics": {
                "totalTokens": 5,
                "promptTokens": 3,
                "outputTokens": 2,
                "latencyMs": 10,
                "estCostUsd": 0.00001,
                "llmCalls": 1,
                "toolCalls": 0,
                "tokensPerSecond": 500.0,
                "billingTier": "free",
            },
            "toolResults": [{"places": [{"id": "places/cafe-lisboa"}]}],
        }

    def run_coordinator(
        self,
        *,
        trip,
        group_preferences,
        category_results,
        trace_id,
        manual_plans=None,
        provider=None,
    ):
        call = {
            "participantIds": [entry.participantId for entry in group_preferences],
            "categories": sorted(category_results),
            "provider": provider,
        }
        if manual_plans is not None:
            call["manualPlanActivities"] = [plan["activity"] for plan in manual_plans]
        self.coordinator_calls.append(call)
        if manual_plans:
            manual_plan = manual_plans[0]
            stop = {
                "time": "20:00",
                "placeId": manual_plan["placeId"],
                "name": manual_plan["activity"],
                "address": manual_plan.get("address") or "Not available",
                "lat": None,
                "lng": None,
                "category": manual_plan["category"],
                "transport": {
                    "mode": "walk",
                    "durationText": "Not available",
                },
                "whyItFits": "User-added manual plan.",
                "suggested": False,
                "source": "manual_plan",
                "manualPlanId": manual_plan["id"],
            }
        else:
            stop = {
                "time": "09:30",
                "placeId": "places/cafe-lisboa",
                "name": "Cafe Lisboa",
                "address": "Rua A, Lisbon",
                "lat": 38.71,
                "lng": -9.14,
                "category": "food_drink",
                "transport": {
                    "mode": "walk",
                    "durationText": "10 mins",
                },
                "whyItFits": "Starts the day with coffee.",
                "suggested": False,
            }
        return {
            "itinerary": {
                "days": [
                    {
                        "date": trip.startDate,
                        "blocks": [
                            {
                                "period": "morning",
                                "stops": [stop],
                            }
                        ],
                    }
                ]
            },
            "metrics": {
                "totalTokens": 20,
                "promptTokens": 12,
                "outputTokens": 8,
                "latencyMs": 50,
                "estCostUsd": 0.00002,
                "llmCalls": 1,
                "toolCalls": 0,
                "tokensPerSecond": 400.0,
                "billingTier": "free",
            },
            "toolResults": [{"places": [{"id": "places/cafe-lisboa"}]}],
        }


def test_adk_runner_tries_next_model_on_quota_error(monkeypatch):
    from app.services import generation

    attempts = []
    runner = generation.AdkGenerationRunner()

    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(
            google_api_key=None,
            groq_api_key=None,
            google_genai_use_vertexai=None,
            agent_model_sequence=[
                "gemini-2.5-flash",
                "gemini-3.5-flash",
                "gemini-3.1-flash-lite",
            ]
        ),
    )

    def fake_run_schema_agent(*, agent, schema, message, user_id, session_id):
        attempts.append((agent.model, session_id))
        if agent.model == "gemini-2.5-flash":
            raise RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded")
        return "output", {"llmCalls": 1}, []

    monkeypatch.setattr(generation, "_run_schema_agent", fake_run_schema_agent)

    output, metrics, tool_results = runner._run_with_model_fallbacks(
        build_agent=lambda model, use_output_schema: SimpleNamespace(model=model),
        schema=object,
        message="go",
        user_id="trace",
        session_id="trace-food",
        model_sequence=[
            "gemini-2.5-flash",
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
        ],
    )

    assert output == "output"
    assert metrics == {"llmCalls": 1}
    assert tool_results == []
    assert attempts == [
        ("gemini-2.5-flash", "trace-food-gemini-2.5-flash"),
        ("gemini-3.5-flash", "trace-food-gemini-3.5-flash"),
    ]


def test_estimated_cost_uses_current_flash_lite_pricing():
    from app.services import generation

    assert generation.estimate_token_cost_usd(
        "gemini-3.1-flash-lite",
        prompt_tokens=1_000_000,
        output_tokens=1_000_000,
    ) == 1.75


def test_admin_can_generate_one_category_result(client, verifier, repo):
    from app.services.generation import get_generation_runner

    runner = ScriptedGenerationRunner()
    client.app.dependency_overrides[get_generation_runner] = lambda: runner
    owner = _user(verifier)
    trip_id = _create_trip(client, owner)
    participant_id = client.get(
        f"/trips/{trip_id}/participants", headers=_auth(owner)
    ).json()[0]["id"]
    participant_id = client.get(
        f"/trips/{trip_id}/participants", headers=_auth(owner)
    ).json()[0]["id"]
    client.put(
        f"/trips/{trip_id}/preferences/participants/{participant_id}/food_drink",
        json={"freeText": "Coffee and seafood", "cuisineInterests": ["seafood"]},
        headers=_auth(owner),
    )

    response = client.post(
        f"/trips/{trip_id}/categories/food_drink/generate", headers=_auth(owner)
    )

    assert response.status_code == 202
    assert response.json() == {"category": "food_drink"}
    result = repo.get(f"trips/{trip_id}/categoryResults", "food_drink")
    assert result["status"] == "complete"
    assert result["candidates"][0]["placeId"] == "places/cafe-lisboa"
    assert result["candidates"][0]["suggested"] is False
    assert result["candidates"][0]["travelersTip"] == (
        "Travelers tip: order the pastry before noon."
    )
    assert result["sourceParticipantIds"] == [participant_id]
    assert result["preferencesVersion"]
    assert result["stale"] is False
    assert result["traceId"]
    assert runner.category_calls == [
        {"category": "food_drink", "participantIds": [participant_id]}
    ]


def test_category_result_exposes_meal_type_when_agent_provides_it(
    client, verifier, repo
):
    from app.services.generation import get_generation_runner

    runner = ScriptedGenerationRunner()
    runner.candidate_overrides = {"meal_type": "breakfast"}
    client.app.dependency_overrides[get_generation_runner] = lambda: runner
    owner = _user(verifier)
    trip_id = _create_trip(client, owner)

    client.post(
        f"/trips/{trip_id}/categories/food_drink/generate", headers=_auth(owner)
    )

    result = repo.get(f"trips/{trip_id}/categoryResults", "food_drink")
    assert result["candidates"][0]["mealType"] == "breakfast"


def test_category_result_omits_meal_type_when_agent_does_not_set_it(
    client, verifier, repo
):
    from app.services.generation import get_generation_runner

    runner = ScriptedGenerationRunner()
    client.app.dependency_overrides[get_generation_runner] = lambda: runner
    owner = _user(verifier)
    trip_id = _create_trip(client, owner)

    client.post(
        f"/trips/{trip_id}/categories/culture_local/generate", headers=_auth(owner)
    )

    result = repo.get(f"trips/{trip_id}/categoryResults", "culture_local")
    assert "mealType" not in result["candidates"][0]


def test_running_category_generation_returns_conflict(client, verifier, repo):
    from app.services.generation import get_generation_runner

    runner = ScriptedGenerationRunner()
    client.app.dependency_overrides[get_generation_runner] = lambda: runner
    owner = _user(verifier)
    trip_id = _create_trip(client, owner)
    repo.update(
        f"trips/{trip_id}/categoryResults",
        "food_drink",
        {
            "status": "running",
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "traceId": "existing",
        },
    )

    response = client.post(
        f"/trips/{trip_id}/categories/food_drink/generate", headers=_auth(owner)
    )

    assert response.status_code == 409
    assert runner.category_calls == []


def test_trip_generation_daily_cap_returns_429(client, verifier, repo):
    from app.core.config import get_settings
    from app.services.generation import get_generation_runner

    runner = ScriptedGenerationRunner()
    client.app.dependency_overrides[get_generation_runner] = lambda: runner
    owner = _user(verifier)
    trip_id = _create_trip(client, owner)
    cap = get_settings().trip_generation_daily_cap
    now = datetime.now(timezone.utc).isoformat()
    for index in range(cap):
        repo.set(
            f"trips/{trip_id}/generations",
            f"gen-{index}",
            {"status": "complete", "startedAt": now},
        )

    response = client.post(f"/trips/{trip_id}/generate", headers=_auth(owner))

    assert response.status_code == 429
    assert "generations for today" in response.json()["detail"]
    assert runner.coordinator_calls == []


def test_generation_quota_reports_remaining_runs(client, verifier, repo):
    from app.core.config import get_settings

    owner = _user(verifier)
    trip_id = _create_trip(client, owner)
    cap = get_settings().trip_generation_daily_cap

    response = client.get(f"/trips/{trip_id}/generation-quota", headers=_auth(owner))
    assert response.status_code == 200
    assert response.json() == {"cap": cap, "usedToday": 0, "remaining": cap}

    now = datetime.now(timezone.utc).isoformat()
    repo.set(
        f"trips/{trip_id}/generations",
        "gen-0",
        {"status": "error", "startedAt": now},
    )

    response = client.get(f"/trips/{trip_id}/generation-quota", headers=_auth(owner))
    assert response.json() == {"cap": cap, "usedToday": 1, "remaining": cap - 1}


def test_trip_generation_cap_ignores_previous_days(client, verifier, repo):
    from app.core.config import get_settings
    from app.services.generation import get_generation_runner

    runner = ScriptedGenerationRunner()
    client.app.dependency_overrides[get_generation_runner] = lambda: runner
    owner = _user(verifier)
    trip_id = _create_trip(client, owner)
    cap = get_settings().trip_generation_daily_cap
    for index in range(cap):
        repo.set(
            f"trips/{trip_id}/generations",
            f"gen-{index}",
            {"status": "complete", "startedAt": "2026-01-01T10:00:00+00:00"},
        )

    response = client.post(f"/trips/{trip_id}/generate", headers=_auth(owner))

    assert response.status_code == 202


def test_coordinator_reuses_fresh_category_results(client, verifier, repo):
    from app.services.generation import get_generation_runner
    from travel_agent.graph import CATEGORY_ORDER

    runner = ScriptedGenerationRunner()
    client.app.dependency_overrides[get_generation_runner] = lambda: runner
    owner = _user(verifier)
    trip_id = _create_trip(client, owner)
    participant_id = client.get(
        f"/trips/{trip_id}/participants", headers=_auth(owner)
    ).json()[0]["id"]
    for category in CATEGORY_ORDER:
        repo.set(
            f"trips/{trip_id}/categoryResults",
            category,
            {
                "status": "complete",
                "candidates": [
                    {
                        "placeId": "places/cafe-lisboa",
                        "name": "Cafe Lisboa",
                        "address": "Rua A, Lisbon",
                        "lat": 38.71,
                        "lng": -9.14,
                        "whyItFits": "Fits the trip.",
                        "timeOfDayFit": "morning",
                        "priceLevel": "$$",
                        "suggested": category != "food_drink",
                    }
                ],
                "toolResults": [{"places": [{"id": "places/cafe-lisboa"}]}],
                "preferencesVersion": "none",
                "traceId": f"{category}-trace",
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            },
        )

    response = client.post(f"/trips/{trip_id}/generate", headers=_auth(owner))

    assert response.status_code == 202
    generation_id = response.json()["generationId"]
    generation = repo.get(f"trips/{trip_id}/generations", generation_id)
    assert generation["status"] == "complete"
    assert generation["phase"] == "done"
    assert generation["agentStatuses"] == {
        **{category: "skipped_fresh" for category in CATEGORY_ORDER},
        "coordinator": "done",
    }
    assert generation["itinerary"]["days"][0]["blocks"][0]["stops"][0]["placeId"] == (
        "places/cafe-lisboa"
    )
    trip = repo.get("trips", trip_id)
    assert trip["status"] == "generated"
    assert trip["latestGenerationId"] == generation_id
    assert runner.category_calls == []
    assert runner.coordinator_calls == [
        {
            "participantIds": [participant_id],
            "categories": sorted(CATEGORY_ORDER),
            "manualPlanActivities": [],
            "provider": None,
        }
    ]


def test_only_trip_admin_can_generate_category(client, verifier, repo):
    from app.services.generation import get_generation_runner
    from app.services.trips import add_member

    runner = ScriptedGenerationRunner()
    client.app.dependency_overrides[get_generation_runner] = lambda: runner
    owner = _user(verifier)
    member = _user(verifier, token="tok-b", uid="user-b", name="Bea")
    trip_id = _create_trip(client, owner)
    add_member(
        repo,
        trip_id,
        CurrentUser(uid="user-b", email="user-b@x.com", display_name="Bea"),
    )

    response = client.post(
        f"/trips/{trip_id}/categories/food_drink/generate", headers=_auth(member)
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"
    assert runner.category_calls == []


def test_only_trip_admin_can_generate_full_itinerary(client, verifier, repo):
    from app.services.generation import get_generation_runner
    from app.services.trips import add_member

    runner = ScriptedGenerationRunner()
    client.app.dependency_overrides[get_generation_runner] = lambda: runner
    owner = _user(verifier)
    member = _user(verifier, token="tok-b", uid="user-b", name="Bea")
    trip_id = _create_trip(client, owner)
    add_member(
        repo,
        trip_id,
        CurrentUser(uid="user-b", email="user-b@x.com", display_name="Bea"),
    )

    response = client.post(f"/trips/{trip_id}/generate", headers=_auth(member))

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"
    assert runner.category_calls == []
    assert runner.coordinator_calls == []


def test_coordinator_receives_manual_plans_without_rerunning_categories(
    client, verifier, repo
):
    from app.services.generation import get_generation_runner
    from tests.test_manual_plans import MANUAL_PLAN
    from travel_agent.graph import CATEGORY_ORDER

    runner = ScriptedGenerationRunner()
    client.app.dependency_overrides[get_generation_runner] = lambda: runner
    owner = _user(verifier)
    trip_id = _create_trip(client, owner)
    participant_id = client.get(
        f"/trips/{trip_id}/participants", headers=_auth(owner)
    ).json()[0]["id"]
    client.post(
        f"/trips/{trip_id}/manual-plans",
        json=MANUAL_PLAN,
        headers=_auth(owner),
    )
    for category in CATEGORY_ORDER:
        repo.set(
            f"trips/{trip_id}/categoryResults",
            category,
            {
                "status": "complete",
                "candidates": [
                    {
                        "placeId": "places/cafe-lisboa",
                        "name": "Cafe Lisboa",
                        "address": "Rua A, Lisbon",
                        "lat": 38.71,
                        "lng": -9.14,
                        "whyItFits": "Fits the trip.",
                        "timeOfDayFit": "morning",
                        "priceLevel": "$$",
                        "suggested": True,
                    }
                ],
                "toolResults": [{"places": [{"id": "places/cafe-lisboa"}]}],
                "preferencesVersion": "none",
                "traceId": f"{category}-trace",
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            },
        )

    response = client.post(f"/trips/{trip_id}/generate", headers=_auth(owner))

    assert response.status_code == 202
    generation = repo.get(
        f"trips/{trip_id}/generations", response.json()["generationId"]
    )
    assert generation["status"] == "complete"
    manual_stop = generation["itinerary"]["days"][0]["blocks"][0]["stops"][0]
    assert manual_stop["placeId"] == "places/time-out-market"
    assert manual_stop["source"] == "manual_plan"
    assert manual_stop["manualPlanId"]
    assert runner.category_calls == []
    assert runner.coordinator_calls == [
        {
            "participantIds": [participant_id],
            "categories": sorted(CATEGORY_ORDER),
            "manualPlanActivities": ["Dinner at Time Out Market"],
            "provider": None,
        }
    ]


def test_coordinator_auto_runs_missing_category_before_planning(client, verifier, repo):
    from app.services.generation import get_generation_runner
    from travel_agent.graph import CATEGORY_ORDER

    runner = ScriptedGenerationRunner()
    client.app.dependency_overrides[get_generation_runner] = lambda: runner
    owner = _user(verifier)
    trip_id = _create_trip(client, owner)
    participant_id = client.get(
        f"/trips/{trip_id}/participants", headers=_auth(owner)
    ).json()[0]["id"]
    for category in CATEGORY_ORDER:
        if category == "nightlife":
            continue
        repo.set(
            f"trips/{trip_id}/categoryResults",
            category,
            {
                "status": "complete",
                "candidates": [
                    {
                        "placeId": "places/cafe-lisboa",
                        "name": "Cafe Lisboa",
                        "address": "Rua A, Lisbon",
                        "lat": 38.71,
                        "lng": -9.14,
                        "whyItFits": "Fits the trip.",
                        "timeOfDayFit": "morning",
                        "priceLevel": "$$",
                        "suggested": True,
                    }
                ],
                "toolResults": [{"places": [{"id": "places/cafe-lisboa"}]}],
                "preferencesVersion": "none",
                "traceId": f"{category}-trace",
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            },
        )

    response = client.post(f"/trips/{trip_id}/generate", headers=_auth(owner))

    assert response.status_code == 202
    generation_id = response.json()["generationId"]
    generation = repo.get(f"trips/{trip_id}/generations", generation_id)
    assert generation["status"] == "complete"
    assert generation["agentStatuses"]["nightlife"] == "done"
    assert runner.category_calls == [
        {"category": "nightlife", "participantIds": [participant_id]}
    ]
    assert sorted(runner.coordinator_calls[0]["categories"]) == sorted(CATEGORY_ORDER)
    missing_result = repo.get(f"trips/{trip_id}/categoryResults", "nightlife")
    assert missing_result["status"] == "complete"
    assert missing_result["candidates"][0]["placeId"] == "places/cafe-lisboa"


def test_coordinator_falls_back_when_missing_category_agent_fails(
    client, verifier, repo
):
    from app.services.generation import get_generation_runner
    from travel_agent.graph import CATEGORY_ORDER

    runner = ScriptedGenerationRunner()
    runner.fail_categories.add("nightlife")
    client.app.dependency_overrides[get_generation_runner] = lambda: runner
    owner = _user(verifier)
    trip_id = _create_trip(client, owner)
    for category in CATEGORY_ORDER:
        if category == "nightlife":
            continue
        repo.set(
            f"trips/{trip_id}/categoryResults",
            category,
            {
                "status": "complete",
                "candidates": [
                    {
                        "placeId": "places/cafe-lisboa",
                        "name": "Cafe Lisboa",
                        "address": "Rua A, Lisbon",
                        "lat": 38.71,
                        "lng": -9.14,
                        "whyItFits": "Fits the trip.",
                        "timeOfDayFit": "morning",
                        "priceLevel": "$$",
                        "suggested": True,
                    }
                ],
                "toolResults": [{"places": [{"id": "places/cafe-lisboa"}]}],
                "preferencesVersion": "none",
                "traceId": f"{category}-trace",
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            },
        )

    response = client.post(f"/trips/{trip_id}/generate", headers=_auth(owner))

    assert response.status_code == 202
    generation = repo.get(
        f"trips/{trip_id}/generations", response.json()["generationId"]
    )
    assert generation["status"] == "complete"
    assert generation["agentStatuses"]["nightlife"] == "fallback"
    result = repo.get(f"trips/{trip_id}/categoryResults", "nightlife")
    assert result["status"] == "complete"
    assert result["fallback"] is True
    assert result["fallbackReason"] == "agent_error"
    assert result["candidates"][0]["suggested"] is True
    assert runner.fallback_calls == [
        {"category": "nightlife", "reason": "agent_error"}
    ]


def test_editing_preferences_marks_category_result_stale(client, verifier, repo):
    from app.services.generation import get_generation_runner

    runner = ScriptedGenerationRunner()
    client.app.dependency_overrides[get_generation_runner] = lambda: runner
    owner = _user(verifier)
    trip_id = _create_trip(client, owner)
    participant_id = client.get(
        f"/trips/{trip_id}/participants", headers=_auth(owner)
    ).json()[0]["id"]
    client.put(
        f"/trips/{trip_id}/preferences/participants/{participant_id}/food_drink",
        json={"freeText": "Coffee"},
        headers=_auth(owner),
    )
    client.post(
        f"/trips/{trip_id}/categories/food_drink/generate", headers=_auth(owner)
    )

    client.put(
        f"/trips/{trip_id}/preferences/participants/{participant_id}/food_drink",
        json={"freeText": "Coffee and seafood"},
        headers=_auth(owner),
    )

    result = repo.get(f"trips/{trip_id}/categoryResults", "food_drink")
    assert result["status"] == "complete"
    assert result["stale"] is True
    assert result["candidates"][0]["placeId"] == "places/cafe-lisboa"


def test_running_trip_generation_returns_existing_generation_id(
    client, verifier, repo
):
    owner = _user(verifier)
    trip_id = _create_trip(client, owner)
    repo.set(
        f"trips/{trip_id}/generations",
        "generation-existing",
        {
            "status": "running",
            "phase": "researching",
            "agentStatuses": {},
            "requestedBy": "user-a",
            "startedAt": datetime.now(timezone.utc).isoformat(),
            "traceId": "trace-existing",
        },
    )

    response = client.post(f"/trips/{trip_id}/generate", headers=_auth(owner))

    assert response.status_code == 409
    assert response.json()["detail"] == {"generationId": "generation-existing"}
