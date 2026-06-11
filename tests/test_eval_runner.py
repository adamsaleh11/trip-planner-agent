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
