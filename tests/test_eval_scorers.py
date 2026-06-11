from evals.scorers import score_groundedness, score_suggested_flag_honesty


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
