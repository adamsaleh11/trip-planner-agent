from evals.scorers import (
    score_candidate_targets,
    score_groundedness,
    score_suggested_flag_honesty,
)


def _candidates(count: int, meal_types: list[str] | None = None) -> list[dict]:
    return [
        {
            "name": f"Place {index}",
            "place_id": f"places/{index}",
            **({"meal_type": meal_types[index]} if meal_types else {}),
        }
        for index in range(count)
    ]


def test_candidate_targets_pass_with_fifteen_per_category_and_meal_split():
    result = score_candidate_targets(
        {
            "food_drink": _candidates(
                15, meal_types=["breakfast"] * 5 + ["lunch_dinner"] * 10
            ),
            "outdoors_scenic": _candidates(15),
            "nightlife": _candidates(15),
            "culture_local": _candidates(15),
            "logistics": _candidates(3),
        }
    )

    assert result.score == 1.0
    assert result.failures == []


def test_candidate_targets_fail_on_low_counts_and_skewed_meal_split():
    result = score_candidate_targets(
        {
            "food_drink": _candidates(
                15, meal_types=["breakfast"] * 1 + ["lunch_dinner"] * 14
            ),
            "outdoors_scenic": _candidates(15),
            "nightlife": _candidates(8),
            "culture_local": _candidates(15),
        }
    )

    assert result.score < 1.0
    assert result.total == 5
    assert result.passed == 3
    assert any("nightlife" in failure for failure in result.failures)
    assert any("breakfast" in failure for failure in result.failures)


ITINERARY = {
    "days": [
        {
            "date": "2026-07-10",
            "blocks": [
                {
                    "name": "morning",
                    "stops": [
                        {
                            "time": "09:00",
                            "placeId": "places/grounded",
                            "name": "Grounded Cafe",
                            "address": "Rua A",
                            "category": "food_drink",
                            "transport": {
                                "mode": "walk",
                                "durationText": "10 mins",
                            },
                            "whyItFits": "Fits.",
                            "suggested": True,
                            "source": "ai_suggestion",
                        },
                        {
                            "time": "11:00",
                            "placeId": "places/hallucinated",
                            "name": "Imaginary View",
                            "address": "Rua B",
                            "category": "outdoors_scenic",
                            "transport": {
                                "mode": "walk",
                                "durationText": "10 mins",
                            },
                            "whyItFits": "Fits.",
                            "suggested": False,
                            "source": "participant_preference",
                        },
                    ],
                }
            ],
        }
    ]
}


def test_groundedness_scores_share_of_non_manual_stops_from_tool_outputs():
    result = score_groundedness(
        ITINERARY,
        tool_results=[{"places": [{"id": "places/grounded"}]}],
    )

    assert result.score == 0.5
    assert result.total == 2
    assert result.passed == 1
    assert result.failures == ["places/hallucinated"]


def test_suggested_flag_honesty_requires_empty_category_stops_to_be_suggested():
    result = score_suggested_flag_honesty(
        ITINERARY,
        empty_categories=["outdoors_scenic"],
    )

    assert result.score == 0.0
    assert result.total == 1
    assert result.failures == ["places/hallucinated"]
