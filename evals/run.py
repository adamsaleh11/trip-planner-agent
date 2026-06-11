from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.data.repository import Repository, get_repository
from app.models.preferences import CATEGORIES, GroupPreferencesEntry
from app.models.trip import Trip
from app.services.generation import AdkGenerationRunner, estimate_token_cost_usd
from evals.scorers import (
    score_constraint_adherence,
    score_groundedness,
    score_schema_validity,
    score_suggested_flag_honesty,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
GOLDEN_SET_PATH = ROOT_DIR / "evals" / "golden_set.json"


EvalExecutor = Callable[[dict[str, Any]], dict[str, Any]]


def run_eval_cases(
    repo: Repository,
    cases: list[dict[str, Any]],
    *,
    executor: EvalExecutor | None = None,
    model: str,
    git_sha: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    run_id = run_id or uuid.uuid4().hex
    executor = executor or execute_live_case
    per_case = []
    for case in cases:
        output = _execute_with_backoff(executor, case)
        scores = _score_case(case, output)
        per_case.append({"caseId": case["id"], "scores": scores})
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "gitSha": git_sha,
        "perCase": per_case,
        "aggregates": _aggregates(per_case),
    }
    repo.set("evalRuns", run_id, result)
    return {"runId": run_id, **result}


def execute_live_case(case: dict[str, Any]) -> dict[str, Any]:
    runner = AdkGenerationRunner()
    trip = Trip(**case["trip"])
    group_preferences = [
        GroupPreferencesEntry.model_validate(entry)
        for entry in case.get("groupPreferences", [])
    ]
    trace_id = uuid.uuid4().hex
    category_results: dict[str, dict[str, Any]] = {}
    all_tool_results: list[dict[str, Any]] = []
    for category in CATEGORIES:
        output = runner.run_category(
            category=category,
            trip=trip,
            group_preferences=group_preferences,
            trace_id=trace_id,
        )
        result = {
            "candidates": output["candidates"],
            "toolResults": output.get("toolResults", []),
        }
        category_results[category] = result
        all_tool_results.extend(result["toolResults"])
    coordinator = runner.run_coordinator(
        trip=trip,
        group_preferences=group_preferences,
        category_results=category_results,
        manual_plans=case.get("manualPlans", []),
        trace_id=trace_id,
        provider="gemini",
    )
    all_tool_results.extend(coordinator.get("toolResults", []))
    all_tool_results.append({"manualPlans": case.get("manualPlans", [])})
    return {"itinerary": coordinator["itinerary"], "toolResults": all_tool_results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="")
    parser.add_argument("--model", default="gemini-3.1-flash-lite")
    args = parser.parse_args()
    cases = _load_cases(args.cases)
    projected = estimate_token_cost_usd(
        args.model,
        prompt_tokens=250_000 * len(cases),
        output_tokens=50_000 * len(cases),
    )
    print(f"Running {len(cases)} eval case(s) sequentially.")
    print(f"Projected scale cost at {args.model}: ${projected:.4f}")
    result = run_eval_cases(
        get_repository(),
        cases,
        model=args.model,
        git_sha=_git_sha(),
    )
    print(json.dumps(result["aggregates"], indent=2, sort_keys=True))
    print(f"Wrote evalRuns/{result['runId']}")


def _load_cases(case_filter: str) -> list[dict[str, Any]]:
    cases = json.loads(GOLDEN_SET_PATH.read_text())
    if not case_filter:
        return cases
    wanted = {case_id.strip() for case_id in case_filter.split(",") if case_id.strip()}
    return [case for case in cases if case["id"] in wanted]


def _execute_with_backoff(executor: EvalExecutor, case: dict[str, Any]) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return executor(case)
        except Exception as exc:
            last_error = exc
            if attempt < 2 and _is_transient(exc):
                time.sleep(2**attempt)
                continue
            raise
    raise RuntimeError(f"Eval case failed after retries: {last_error}")


def _score_case(case: dict[str, Any], output: dict[str, Any]) -> dict[str, float]:
    itinerary = output["itinerary"]
    tool_results = output.get("toolResults", [])
    return {
        "schemaValidity": score_schema_validity(itinerary).score,
        "groundedness": score_groundedness(itinerary, tool_results).score,
        "constraintAdherence": score_constraint_adherence(
            itinerary,
            case.get("constraints", []),
        ).score,
        "suggestedFlagHonesty": score_suggested_flag_honesty(
            itinerary,
            case.get("emptyCategories", []),
        ).score,
    }


def _aggregates(per_case: list[dict[str, Any]]) -> dict[str, float]:
    keys = [
        "schemaValidity",
        "groundedness",
        "constraintAdherence",
        "suggestedFlagHonesty",
    ]
    if not per_case:
        return {key: 0.0 for key in keys}
    return {
        key: round(
            sum(case["scores"][key] for case in per_case) / len(per_case),
            4,
        )
        for key in keys
    }


def _is_transient(exc: Exception) -> bool:
    text = str(exc).lower()
    return "503" in text or "high demand" in text or "unavailable" in text


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT_DIR,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    main()
