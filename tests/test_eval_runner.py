from tests.conftest import FakeRepository


def test_eval_runner_scores_cases_and_writes_eval_run():
    from evals.run import run_eval_cases

    repo = FakeRepository()
    cases = [
        {
            "id": "grounded-empty-food",
            "emptyCategories": ["food_drink"],
            "constraints": [],
        }
    ]

    def executor(case):
        return {
            "itinerary": {
                "days": [
                    {
                        "date": "2026-07-10",
                        "blocks": [
                            {
                                "name": "morning",
                                "stops": [
                                    {
                                        "time": "09:00",
                                        "placeId": "places/cafe",
                                        "name": "Cafe",
                                        "address": "Rua A",
                                        "category": "food_drink",
                                        "transport": {
                                            "mode": "walk",
                                            "durationText": "10 mins",
                                        },
                                        "whyItFits": "Inferred breakfast.",
                                        "suggested": True,
                                        "source": "ai_suggestion",
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
            "toolResults": [{"places": [{"id": "places/cafe"}]}],
        }

    result = run_eval_cases(
        repo,
        cases,
        executor=executor,
        model="gemini-3.1-flash-lite",
        git_sha="abc123",
        run_id="eval-test",
    )

    stored = repo.get("evalRuns", "eval-test")
    assert result["aggregates"] == {
        "schemaValidity": 1.0,
        "groundedness": 1.0,
        "constraintAdherence": 1.0,
        "suggestedFlagHonesty": 1.0,
    }
    assert stored["model"] == "gemini-3.1-flash-lite"
    assert stored["gitSha"] == "abc123"
    assert stored["perCase"][0]["caseId"] == "grounded-empty-food"


def test_eval_runner_scores_candidate_targets_when_category_candidates_present():
    from evals.run import run_eval_cases

    repo = FakeRepository()
    cases = [{"id": "volume-case", "emptyCategories": [], "constraints": []}]

    def executor(case):
        def places(count, meal_types=None):
            return [
                {
                    "name": f"Place {index}",
                    "place_id": f"places/{index}",
                    **({"meal_type": meal_types[index]} if meal_types else {}),
                }
                for index in range(count)
            ]

        return {
            "itinerary": {
                "days": [{"date": "2026-07-10", "blocks": []}]
            },
            "toolResults": [],
            "categoryCandidates": {
                "food_drink": places(
                    15, meal_types=["breakfast"] * 5 + ["lunch_dinner"] * 10
                ),
                "outdoors_scenic": places(15),
                "nightlife": places(15),
                "culture_local": places(15),
                "logistics": places(3),
            },
        }

    result = run_eval_cases(
        repo,
        cases,
        executor=executor,
        model="gemini-3.1-flash-lite",
        git_sha="abc123",
        run_id="eval-volume",
    )

    assert result["perCase"][0]["scores"]["candidateTargets"] == 1.0
    assert result["aggregates"]["candidateTargets"] == 1.0
