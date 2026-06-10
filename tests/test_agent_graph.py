import pytest

from app.models.preferences import GroupPreferencesEntry, MemberPreferences
from app.models.trip import Destination, Trip
from travel_agent.graph import (
    CATEGORY_ORDER,
    MAX_PLACES_QUERIES_PER_CATEGORY,
    MAX_ROUTE_ESTIMATES_PER_GENERATION,
    ToolCallBudget,
    build_category_agent,
    build_coordinator_agent,
    validate_itinerary_grounding,
)
from travel_agent.schemas import Itinerary


def _trip() -> Trip:
    return Trip(
        id="trip-lisbon",
        name="Lisbon week",
        destination=Destination(text="Lisbon, Portugal", lat=38.7223, lng=-9.1393),
        startDate="2026-07-01",
        endDate="2026-07-03",
        lodgingArea="Baixa",
        adminUid="owner",
        createdAt="2026-06-10T00:00:00Z",
    )


def _group() -> list[GroupPreferencesEntry]:
    return [
        GroupPreferencesEntry.model_validate(
            {
                "uid": "u1",
                "participantId": "p1",
                "displayName": "Alex",
                "preferences": {
                    "food_drink": {
                        "freeText": "Find grilled sardines and a low-key coffee stop.",
                        "dietaryRestrictions": ["gluten_free"],
                        "cuisineInterests": ["seafood", "pastel de nata"],
                        "mealBudget": "$$",
                    },
                    "outdoors_scenic": {
                        "freeText": "Sunset viewpoints and not too much climbing.",
                        "activityLevel": "moderate",
                        "interests": ["viewpoints", "sunsets"],
                    },
                },
            }
        ),
        GroupPreferencesEntry.model_validate(
            {
                "uid": "u2",
                "participantId": "p2",
                "displayName": "Blair",
                "preferences": {
                    "food_drink": {
                        "freeText": "Natural wine would be great.",
                        "dietaryRestrictions": ["none"],
                        "drinkInterests": ["local_drinks"],
                    },
                    "logistics": {
                        "pace": "balanced",
                        "transport": ["walk", "transit"],
                        "mobilityNotes": "Avoid long steep walks.",
                    },
                },
            }
        ),
    ]


def test_category_agent_instruction_contains_trip_and_member_preferences():
    agent = build_category_agent("food_drink", _trip(), _group())

    assert agent.name == "food_drink_agent"
    assert agent.model == "gemini-2.5-flash"
    assert "Lisbon, Portugal" in agent.instruction
    assert "2026-07-01 to 2026-07-03" in agent.instruction
    assert "Baixa" in agent.instruction
    assert "Group size: 2" in agent.instruction
    assert "Alex" in agent.instruction
    assert "grilled sardines" in agent.instruction
    assert "gluten_free" in agent.instruction
    assert "Natural wine" in agent.instruction
    assert "suggested=false" in agent.instruction


def test_empty_category_agent_uses_inference_context_and_marks_all_suggested():
    agent = build_category_agent("nightlife", _trip(), _group())

    assert "No member filled nightlife preferences" in agent.instruction
    assert "Infer a best-fit nightlife profile" in agent.instruction
    assert "Every candidate you output for this category must set suggested=true" in agent.instruction
    assert "food_drink" in agent.instruction
    assert "Find grilled sardines" in agent.instruction
    assert "outdoors_scenic" in agent.instruction
    assert "Sunset viewpoints" in agent.instruction


def test_food_agent_instruction_treats_diet_and_mobility_as_hard_filters():
    agent = build_category_agent("food_drink", _trip(), _group())

    assert "Dietary restrictions and mobility notes are hard filters" in agent.instruction
    assert "never preferences to balance" in agent.instruction
    assert "Avoid long steep walks" in agent.instruction


def test_builders_are_per_request_and_use_expected_tools():
    first = build_category_agent("logistics", _trip(), _group())
    second = build_category_agent("logistics", _trip(), _group())
    coordinator = build_coordinator_agent(_trip())

    assert first is not second
    assert [tool.__name__ for tool in first.tools] == [
        "search_location_options",
        "estimate_route_time",
        "search_collective_memory",
    ]
    assert [tool.__name__ for tool in coordinator.tools] == ["estimate_route_time"]
    assert coordinator.output_schema is Itinerary


def test_final_itinerary_schema_validates_days_blocks_and_stops():
    itinerary = Itinerary.model_validate(
        {
            "days": [
                {
                    "date": "2026-07-01",
                    "blocks": [
                        {
                            "period": "morning",
                            "stops": [
                                {
                                    "time": "09:30",
                                    "placeId": "places/abc",
                                    "name": "Cafe Lisboa",
                                    "address": "Rua A, Lisbon",
                                    "lat": 38.71,
                                    "lng": -9.14,
                                    "category": "food_drink",
                                    "transport": {
                                        "mode": "walk",
                                        "durationText": "12 mins",
                                    },
                                    "whyItFits": "Matches coffee and budget preferences.",
                                    "suggested": False,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )

    assert itinerary.days[0].blocks[0].stops[0].suggested is False


def test_itinerary_grounding_requires_places_from_captured_tool_results():
    itinerary = Itinerary.model_validate(
        {
            "days": [
                {
                    "date": "2026-07-01",
                    "blocks": [
                        {
                            "period": "evening",
                            "stops": [
                                {
                                    "time": "20:00",
                                    "placeId": "places/not-from-tool",
                                    "name": "Invented Bar",
                                    "address": "Not available",
                                    "lat": 38.0,
                                    "lng": -9.0,
                                    "category": "nightlife",
                                    "transport": {
                                        "mode": "transit",
                                        "durationText": "Not available",
                                    },
                                    "whyItFits": "Looks fun.",
                                    "suggested": True,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )

    with pytest.raises(ValueError, match="not-from-tool"):
        validate_itinerary_grounding(
            itinerary,
            [{"results": [{"places": [{"id": "places/real"}]}]}],
        )


def test_tool_call_budget_enforces_generation_limits():
    budget = ToolCallBudget()

    for _ in range(MAX_PLACES_QUERIES_PER_CATEGORY):
        budget.record_places_query("food_drink")
    with pytest.raises(RuntimeError, match="Places query budget exceeded"):
        budget.record_places_query("food_drink")

    for _ in range(MAX_ROUTE_ESTIMATES_PER_GENERATION):
        budget.record_route_estimate()
    with pytest.raises(RuntimeError, match="Route estimate budget exceeded"):
        budget.record_route_estimate()


def test_all_categories_are_supported():
    assert CATEGORY_ORDER == [
        "food_drink",
        "outdoors_scenic",
        "nightlife",
        "culture_local",
        "logistics",
    ]
    empty_group = [
        GroupPreferencesEntry(
            participantId="empty", displayName=None, preferences=MemberPreferences()
        )
    ]
    assert {build_category_agent(category, _trip(), empty_group).name for category in CATEGORY_ORDER} == {
        f"{category}_agent" for category in CATEGORY_ORDER
    }
