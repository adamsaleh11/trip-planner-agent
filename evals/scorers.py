from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from travel_agent.graph import (
    EXPERIENCE_CATEGORIES,
    TARGET_CANDIDATES_PER_EXPERIENCE_CATEGORY,
)
from travel_agent.schemas import Itinerary

BREAKFAST_SHARE = 1 / 3
BREAKFAST_COUNT_TOLERANCE = 1


@dataclass(frozen=True)
class ScoreResult:
    score: float
    passed: int
    total: int
    failures: list[str]


def score_schema_validity(itinerary: dict[str, Any]) -> ScoreResult:
    try:
        Itinerary.model_validate(itinerary)
    except Exception as exc:
        return ScoreResult(score=0.0, passed=0, total=1, failures=[str(exc)])
    return ScoreResult(score=1.0, passed=1, total=1, failures=[])


def score_groundedness(
    itinerary: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> ScoreResult:
    model = Itinerary.model_validate(itinerary)
    known_place_ids = _collect_place_ids(tool_results)
    stops = [
        stop
        for day in model.days
        for block in day.blocks
        for stop in block.stops
        if stop.source != "manual_plan"
    ]
    failures = [stop.placeId for stop in stops if stop.placeId not in known_place_ids]
    return _ratio(len(stops) - len(failures), len(stops), failures)


def score_suggested_flag_honesty(
    itinerary: dict[str, Any],
    empty_categories: list[str],
) -> ScoreResult:
    model = Itinerary.model_validate(itinerary)
    empty = set(empty_categories)
    checked = [
        stop
        for day in model.days
        for block in day.blocks
        for stop in block.stops
        if stop.category in empty and stop.source != "manual_plan"
    ]
    failures = [stop.placeId for stop in checked if not stop.suggested]
    return _ratio(len(checked) - len(failures), len(checked), failures)


def score_constraint_adherence(
    itinerary: dict[str, Any],
    constraints: list[dict[str, Any]],
) -> ScoreResult:
    model = Itinerary.model_validate(itinerary)
    failures: list[str] = []
    for constraint in constraints:
        if constraint.get("kind") == "forbidden_name_terms":
            terms = [str(term).lower() for term in constraint.get("terms", [])]
            for day in model.days:
                for block in day.blocks:
                    for stop in block.stops:
                        haystack = f"{stop.name} {stop.whyItFits}".lower()
                        if any(term in haystack for term in terms):
                            failures.append(stop.placeId)
    return _ratio(1 if not failures else 0, 1, sorted(set(failures)))


def score_candidate_targets(
    category_candidates: dict[str, list[dict[str, Any]]],
) -> ScoreResult:
    failures: list[str] = []
    checks = 0
    for category in EXPERIENCE_CATEGORIES:
        checks += 1
        count = len(category_candidates.get(category, []))
        if count != TARGET_CANDIDATES_PER_EXPERIENCE_CATEGORY:
            failures.append(
                f"{category}: expected "
                f"{TARGET_CANDIDATES_PER_EXPERIENCE_CATEGORY} candidates, got {count}"
            )

    checks += 1
    food = category_candidates.get("food_drink", [])
    breakfast_count = sum(
        1 for candidate in food if candidate.get("meal_type") == "breakfast"
    )
    expected_breakfast = len(food) * BREAKFAST_SHARE
    if not food or abs(breakfast_count - expected_breakfast) > BREAKFAST_COUNT_TOLERANCE:
        failures.append(
            f"food_drink: expected ~{expected_breakfast:.1f} breakfast spots "
            f"of {len(food)}, got {breakfast_count}"
        )
    return _ratio(checks - len(failures), checks, failures)


def _ratio(passed: int, total: int, failures: list[str]) -> ScoreResult:
    if total == 0:
        return ScoreResult(score=1.0, passed=0, total=0, failures=[])
    return ScoreResult(
        score=round(passed / total, 4),
        passed=passed,
        total=total,
        failures=failures,
    )


def _collect_place_ids(payload: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"id", "placeId", "place_id"} and isinstance(value, str):
                found.add(value)
            found.update(_collect_place_ids(value))
    elif isinstance(payload, list):
        for item in payload:
            found.update(_collect_place_ids(item))
    return found
