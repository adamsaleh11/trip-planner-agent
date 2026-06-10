from __future__ import annotations

import time
import uuid
import json
import os
from datetime import datetime, timezone
from typing import Any, Protocol

from fastapi import BackgroundTasks, HTTPException

from app.core.auth import CurrentUser
from app.data.repository import Repository
from app.models.preferences import CATEGORIES, GroupPreferencesEntry
from app.models.trip import Trip
from app.services import manual_plans as manual_plans_service
from app.services import preferences as prefs_service
from app.services import trips as trips_service


CATEGORY_RUNNING_STALE_SECONDS = 5 * 60


class GenerationRunner(Protocol):
    def run_category(
        self,
        *,
        category: str,
        trip: Trip,
        group_preferences: list[GroupPreferencesEntry],
        trace_id: str,
    ) -> dict[str, Any]:
        ...

    def run_coordinator(
        self,
        *,
        trip: Trip,
        group_preferences: list[GroupPreferencesEntry],
        category_results: dict[str, dict[str, Any]],
        manual_plans: list[dict[str, Any]],
        trace_id: str,
    ) -> dict[str, Any]:
        ...

    def run_category_fallback(
        self,
        *,
        category: str,
        trip: Trip,
        group_preferences: list[GroupPreferencesEntry],
        trace_id: str,
        reason: str,
    ) -> dict[str, Any]:
        ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _category_results_collection(trip_id: str) -> str:
    return f"{trips_service.TRIPS_COLLECTION}/{trip_id}/categoryResults"


def _generations_collection(trip_id: str) -> str:
    return f"{trips_service.TRIPS_COLLECTION}/{trip_id}/generations"


def _preferences_version(repo: Repository, trip_id: str, category: str) -> str:
    versions = []
    for _, data in repo.list(f"{trips_service.TRIPS_COLLECTION}/{trip_id}/preferences"):
        updated_at = data.get("_updatedAt", {}).get(category)
        if updated_at:
            versions.append(updated_at)
    return max(versions) if versions else "none"


def request_category_generation(
    repo: Repository,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    trip_id: str,
    category: str,
    runner: GenerationRunner,
) -> dict[str, str]:
    if category not in CATEGORIES:
        raise HTTPException(status_code=404, detail="Unknown preference category")
    trip = trips_service.require_member(repo, trip_id, user.uid)
    existing = repo.get(_category_results_collection(trip_id), category)
    if _is_running(existing):
        raise HTTPException(status_code=409, detail="Category generation already running")
    trace_id = uuid.uuid4().hex
    repo.update(
        _category_results_collection(trip_id),
        category,
        {
            "status": "running",
            "candidates": [],
            "sourceParticipantIds": [],
            "metrics": _empty_metrics(),
            "traceId": trace_id,
            "updatedAt": _now(),
            "startedAt": _now(),
            "preferencesVersion": _preferences_version(repo, trip_id, category),
            "stale": False,
            "fallback": False,
            "fallbackReason": None,
            "error": None,
        },
    )
    background_tasks.add_task(
        _run_category_job,
        repo,
        trip,
        user.uid,
        category,
        runner,
        trace_id,
    )
    return {"category": category}


def request_trip_generation(
    repo: Repository,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    trip_id: str,
    runner: GenerationRunner,
) -> dict[str, str]:
    trip = trips_service.require_admin(repo, trip_id, user.uid)
    running_generation = _running_generation_id(repo, trip_id)
    if running_generation:
        raise HTTPException(
            status_code=409,
            detail={"generationId": running_generation},
        )
    generation_id = uuid.uuid4().hex
    trace_id = uuid.uuid4().hex
    repo.set(
        _generations_collection(trip_id),
        generation_id,
        {
            "status": "running",
            "phase": "collecting_preferences",
            "agentStatuses": {**{category: "pending" for category in CATEGORIES}, "coordinator": "pending"},
            "requestedBy": user.uid,
            "startedAt": _now(),
            "traceId": trace_id,
        },
    )
    background_tasks.add_task(
        _run_trip_generation_job,
        repo,
        trip,
        user.uid,
        generation_id,
        runner,
        trace_id,
    )
    return {"generationId": generation_id}


def _running_generation_id(repo: Repository, trip_id: str) -> str | None:
    for generation_id, data in repo.list(_generations_collection(trip_id)):
        if data.get("status") == "running":
            return generation_id
    return None


def _is_running(existing: dict | None) -> bool:
    if not existing or existing.get("status") != "running":
        return False
    updated_at = existing.get("updatedAt") or existing.get("startedAt")
    if not updated_at:
        return True
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(updated_at)
    except ValueError:
        return True
    return age.total_seconds() < CATEGORY_RUNNING_STALE_SECONDS


def _run_category_job(
    repo: Repository,
    trip: Trip,
    uid: str,
    category: str,
    runner: GenerationRunner,
    trace_id: str,
) -> None:
    collection = _category_results_collection(trip.id)
    try:
        group_preferences = prefs_service.get_group_preferences(repo, trip.id, uid)
        version = _preferences_version(repo, trip.id, category)
        output = runner.run_category(
            category=category,
            trip=trip,
            group_preferences=group_preferences,
            trace_id=trace_id,
        )
        _write_category_complete(
            repo,
            trip.id,
            category,
            group_preferences,
            output,
            trace_id,
            version,
        )
    except Exception as exc:
        repo.update(
            collection,
            category,
            {
                "status": "error",
                "candidates": [],
                "sourceParticipantIds": [],
                "metrics": _empty_metrics(),
                "traceId": trace_id,
                "updatedAt": _now(),
                "preferencesVersion": _preferences_version(repo, trip.id, category),
                "stale": False,
                "fallback": False,
                "fallbackReason": None,
                "error": _user_generation_error(
                    exc,
                    "Category generation failed. Please try again.",
                ),
                "errorDetail": str(exc),
            },
        )


def _run_trip_generation_job(
    repo: Repository,
    trip: Trip,
    uid: str,
    generation_id: str,
    runner: GenerationRunner,
    trace_id: str,
) -> None:
    generation_collection = _generations_collection(trip.id)
    try:
        group_preferences = prefs_service.get_group_preferences(repo, trip.id, uid)
        repo.update(
            generation_collection,
            generation_id,
            {"phase": "researching"},
        )
        category_results: dict[str, dict[str, Any]] = {}
        agent_statuses = {**{category: "pending" for category in CATEGORIES}, "coordinator": "pending"}
        for category in CATEGORIES:
            result = repo.get(_category_results_collection(trip.id), category)
            if _is_fresh_category_result(repo, trip.id, category, result):
                category_results[category] = result or {}
                agent_statuses[category] = "skipped_fresh"
            else:
                agent_statuses[category] = "running"
                repo.update(
                    generation_collection,
                    generation_id,
                    {"agentStatuses": agent_statuses},
                )
                version = _preferences_version(repo, trip.id, category)
                fallback = False
                fallback_reason = None
                try:
                    output = runner.run_category(
                        category=category,
                        trip=trip,
                        group_preferences=group_preferences,
                        trace_id=trace_id,
                    )
                    next_status = "done"
                except Exception:
                    fallback = True
                    fallback_reason = "agent_error"
                    output = runner.run_category_fallback(
                        category=category,
                        trip=trip,
                        group_preferences=group_preferences,
                        trace_id=trace_id,
                        reason=fallback_reason,
                    )
                    next_status = "fallback"
                category_results[category] = _write_category_complete(
                    repo,
                    trip.id,
                    category,
                    group_preferences,
                    output,
                    trace_id,
                    version,
                    fallback=fallback,
                    fallback_reason=fallback_reason,
                )
                agent_statuses[category] = next_status
        repo.update(
            generation_collection,
            generation_id,
            {"agentStatuses": agent_statuses, "phase": "building_itinerary"},
        )
        agent_statuses["coordinator"] = "running"
        repo.update(
            generation_collection,
            generation_id,
            {"agentStatuses": agent_statuses},
        )
        manual_plans = [
            plan.model_dump()
            for plan in manual_plans_service.list_manual_plans(repo, trip.id, uid)
        ]
        output = runner.run_coordinator(
            trip=trip,
            group_preferences=group_preferences,
            category_results=category_results,
            manual_plans=manual_plans,
            trace_id=trace_id,
        )
        itinerary = output["itinerary"]
        _validate_itinerary(
            itinerary, category_results, output.get("toolResults", []), manual_plans
        )
        agent_statuses["coordinator"] = "done"
        repo.update(
            generation_collection,
            generation_id,
            {
                "status": "complete",
                "phase": "done",
                "agentStatuses": agent_statuses,
                "itinerary": itinerary,
                "metrics": output.get("metrics", _empty_metrics()),
                "updatedAt": _now(),
                "error": None,
            },
        )
        repo.update(
            trips_service.TRIPS_COLLECTION,
            trip.id,
            {"status": "generated", "latestGenerationId": generation_id},
        )
    except Exception as exc:
        repo.update(
            generation_collection,
            generation_id,
            {
                "status": "error",
                "phase": "done",
                "updatedAt": _now(),
                "error": _user_generation_error(exc, "Trip generation failed. Please try again."),
                "errorDetail": str(exc),
            },
        )


def _is_fresh_category_result(
    repo: Repository, trip_id: str, category: str, result: dict | None
) -> bool:
    if not result or result.get("status") != "complete":
        return False
    return result.get("preferencesVersion", "none") >= _preferences_version(
        repo, trip_id, category
    )


def _validate_itinerary(
    itinerary: dict[str, Any],
    category_results: dict[str, dict[str, Any]],
    coordinator_tool_results: list[dict[str, Any]],
    manual_plans: list[dict[str, Any]] | None = None,
) -> None:
    from travel_agent.graph import validate_itinerary_grounding
    from travel_agent.schemas import Itinerary

    model = Itinerary.model_validate(itinerary)
    captured_tool_results = [
        *(result.get("toolResults", []) for result in category_results.values()),
        coordinator_tool_results,
        {"manualPlans": manual_plans or []},
    ]
    validate_itinerary_grounding(model, captured_tool_results)


def _write_category_complete(
    repo: Repository,
    trip_id: str,
    category: str,
    group_preferences: list[GroupPreferencesEntry],
    output: dict[str, Any],
    trace_id: str,
    preferences_version: str,
    fallback: bool = False,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    data = {
        "status": "complete",
        "candidates": [
            _candidate_to_contract(candidate) for candidate in output["candidates"]
        ],
        "sourceParticipantIds": [
            entry.participantId
            for entry in group_preferences
            if getattr(entry.preferences, category) is not None
        ],
        "metrics": output.get("metrics", _empty_metrics()),
        "toolResults": output.get("toolResults", []),
        "traceId": trace_id,
        "updatedAt": _now(),
        "preferencesVersion": preferences_version,
        "stale": False,
        "error": None,
        "fallback": fallback,
        "fallbackReason": fallback_reason,
    }
    repo.update(_category_results_collection(trip_id), category, data)
    return data


def _candidate_to_contract(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "placeId": candidate["place_id"],
        "name": candidate["name"],
        "address": candidate["address"],
        "lat": candidate.get("lat"),
        "lng": candidate.get("lng"),
        "whyItFits": candidate["why_it_fits"],
        "timeOfDayFit": candidate["time_of_day_fit"],
        "priceLevel": candidate.get("estimated_price_level", "Not available"),
        "suggested": candidate["suggested"],
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "totalTokens": 0,
        "promptTokens": 0,
        "outputTokens": 0,
        "latencyMs": 0,
        "estCostUsd": 0.0,
        "llmCalls": 0,
        "toolCalls": 0,
        "tokensPerSecond": 0.0,
        "billingTier": "free",
    }


def _settings():
    from app.core.config import get_settings

    return get_settings()


def _configure_llm_environment() -> None:
    settings = _settings()
    if settings.google_api_key:
        os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
    if settings.groq_api_key:
        os.environ.setdefault("GROQ_API_KEY", settings.groq_api_key)
    if settings.google_genai_use_vertexai is not None:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = (
            "true" if settings.google_genai_use_vertexai else "false"
        )


def _use_adk_output_schema(model: str) -> bool:
    # Groq rejects response_format/json mode combined with tool calling. Keep
    # ADK tools enabled and validate the final JSON text locally instead.
    return not model.startswith("groq/")


def _model_message(message: str, schema, use_output_schema: bool) -> str:
    if use_output_schema:
        return message
    schema_json = json.dumps(schema.model_json_schema(), sort_keys=True)
    return (
        f"{message}\n\n"
        "Return only valid JSON matching this JSON Schema. Do not wrap it in "
        f"markdown or prose.\nJSON Schema: {schema_json}"
    )


class AdkGenerationRunner:
    def _run_with_model_fallbacks(
        self,
        *,
        build_agent,
        schema,
        message: str,
        user_id: str,
        session_id: str,
        model_sequence: list[str],
    ):
        last_error: Exception | None = None
        _configure_llm_environment()
        for model in model_sequence:
            try:
                use_output_schema = _use_adk_output_schema(model)
                return _run_schema_agent(
                    agent=build_agent(model, use_output_schema),
                    schema=schema,
                    message=_model_message(message, schema, use_output_schema),
                    user_id=user_id,
                    session_id=f"{session_id}-{model}",
                )
            except Exception as exc:
                last_error = exc
                if _should_try_next_model(exc):
                    continue
                raise
        raise RuntimeError(f"All configured LLM models failed: {last_error}")

    def run_category(
        self,
        *,
        category: str,
        trip: Trip,
        group_preferences: list[GroupPreferencesEntry],
        trace_id: str,
    ) -> dict[str, Any]:
        from travel_agent.graph import build_category_agent
        from travel_agent.schemas import CategoryCandidateList

        output, metrics, tool_results = self._run_with_model_fallbacks(
            build_agent=lambda model, use_output_schema: build_category_agent(
                category,
                trip,
                group_preferences,
                model=model,
                use_output_schema=use_output_schema,
            ),
            schema=CategoryCandidateList,
            message=f"Generate grounded {category} candidates for this trip now.",
            user_id=trace_id,
            session_id=f"{trace_id}-{category}",
            model_sequence=_settings().agent_category_model_sequence,
        )
        return {
            "candidates": [candidate.model_dump() for candidate in output.candidates],
            "metrics": metrics,
            "toolResults": tool_results,
        }

    def run_coordinator(
        self,
        *,
        trip: Trip,
        group_preferences: list[GroupPreferencesEntry],
        category_results: dict[str, dict[str, Any]],
        manual_plans: list[dict[str, Any]],
        trace_id: str,
    ) -> dict[str, Any]:
        from travel_agent.graph import build_coordinator_agent
        from travel_agent.schemas import Itinerary

        message = json.dumps(
            {
                "categoryResults": category_results,
                "groupPreferences": [
                    entry.model_dump(exclude_none=True) for entry in group_preferences
                ],
                "manualPlans": manual_plans,
            },
            sort_keys=True,
        )
        output, metrics, tool_results = self._run_with_model_fallbacks(
            build_agent=lambda model, use_output_schema: build_coordinator_agent(
                trip,
                model=model,
                use_output_schema=use_output_schema,
            ),
            schema=Itinerary,
            message=message,
            user_id=trace_id,
            session_id=f"{trace_id}-coordinator",
            model_sequence=_settings().agent_coordinator_model_sequence,
        )
        return {
            "itinerary": output.model_dump(),
            "metrics": metrics,
            "toolResults": tool_results,
        }

    def run_category_fallback(
        self,
        *,
        category: str,
        trip: Trip,
        group_preferences: list[GroupPreferencesEntry],
        trace_id: str,
        reason: str,
    ) -> dict[str, Any]:
        from app.models.preferences import GroupPreferencesEntry as PreferencesEntry
        from app.models.preferences import MemberPreferences
        from travel_agent.graph import build_category_agent
        from travel_agent.schemas import CategoryCandidateList

        generic_preferences = [
            PreferencesEntry(
                participantId=entry.participantId,
                displayName=entry.displayName,
                claimedByUid=entry.claimedByUid,
                preferences=MemberPreferences(),
            )
            for entry in group_preferences
        ]
        output, metrics, tool_results = self._run_with_model_fallbacks(
            build_agent=lambda model, use_output_schema: build_category_agent(
                category,
                trip,
                generic_preferences,
                model=model,
                use_output_schema=use_output_schema,
            ),
            schema=CategoryCandidateList,
            message=(
                f"Generate fallback {category} candidates after {reason}. "
                "Use generic destination preferences, other trip context, and any "
                "available memory/tool results. Keep suggested as item-level provenance."
            ),
            user_id=trace_id,
            session_id=f"{trace_id}-{category}-fallback",
            model_sequence=_settings().agent_category_model_sequence,
        )
        return {
            "candidates": [candidate.model_dump() for candidate in output.candidates],
            "metrics": metrics,
            "toolResults": tool_results,
        }


def _run_schema_agent(agent, schema, message: str, user_id: str, session_id: str):
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    _configure_llm_environment()

    last_error: Exception | None = None
    for attempt in range(3):
        start = time.monotonic()
        try:
            session_service = InMemorySessionService()
            session_service.create_session_sync(
                app_name="trip_planner_agent",
                user_id=user_id,
                session_id=session_id,
            )
            runner = Runner(
                app_name="trip_planner_agent",
                agent=agent,
                session_service=session_service,
            )
            content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=message)],
            )
            events = list(
                runner.run(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=content,
                )
            )
            output = _extract_schema_output(events, schema)
            return output, _metrics_from_events(events, start), _tool_results_from_events(events)
        except Exception as exc:
            last_error = exc
            if attempt < 2 and _is_transient_llm_error(exc):
                time.sleep(2**attempt)
                continue
            raise
    raise RuntimeError(f"Agent failed after retries: {last_error}")


def _extract_schema_output(events: list[Any], schema):
    for event in reversed(events):
        error_code = getattr(event, "error_code", None)
        error_message = getattr(event, "error_message", None)
        if error_code or error_message:
            raise RuntimeError(
                ": ".join(
                    part
                    for part in [str(error_code or ""), str(error_message or "")]
                    if part
                )
            )
        output = getattr(event, "output", None)
        if output is not None:
            return schema.model_validate(output)
        actions = getattr(event, "actions", None)
        model_response = getattr(actions, "set_model_response", None)
        if model_response is not None:
            return schema.model_validate(model_response)
        content = getattr(event, "content", None)
        for part in getattr(content, "parts", []) or []:
            function_call = getattr(part, "function_call", None)
            if (
                function_call is not None
                and getattr(function_call, "name", None) == "set_model_response"
            ):
                return schema.model_validate(getattr(function_call, "args", {}) or {})
            response = getattr(part, "function_response", None)
            if response is not None and getattr(response, "name", None) == "set_model_response":
                response_payload = (
                    getattr(response, "response", None)
                    or getattr(response, "result", None)
                    or {}
                )
                return schema.model_validate(response_payload)
            text = getattr(part, "text", None)
            if text:
                try:
                    return schema.model_validate_json(text)
                except Exception:
                    try:
                        return schema.model_validate(json.loads(text))
                    except Exception:
                        continue
    raise RuntimeError("Agent did not return schema output")


def _metrics_from_events(events: list[Any], start: float) -> dict[str, Any]:
    prompt_tokens = 0
    output_tokens = 0
    total_tokens = 0
    for event in events:
        usage = getattr(event, "usage_metadata", None)
        prompt_tokens += int(getattr(usage, "prompt_token_count", 0) or 0)
        output_tokens += int(getattr(usage, "candidates_token_count", 0) or 0)
        total_tokens += int(getattr(usage, "total_token_count", 0) or 0)
    if total_tokens == 0:
        total_tokens = prompt_tokens + output_tokens
    latency_ms = int((time.monotonic() - start) * 1000)
    return {
        "totalTokens": total_tokens,
        "promptTokens": prompt_tokens,
        "outputTokens": output_tokens,
        "latencyMs": latency_ms,
        "estCostUsd": _estimate_cost(prompt_tokens, output_tokens),
        "llmCalls": 1,
        "toolCalls": len(_tool_results_from_events(events)),
        "tokensPerSecond": round(total_tokens / max(latency_ms / 1000, 0.001), 2),
        "billingTier": _billing_tier(),
    }


def _tool_results_from_events(events: list[Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for event in events:
        content = getattr(event, "content", None)
        for part in getattr(content, "parts", []) or []:
            response = getattr(part, "function_response", None)
            if response is not None:
                results.append(
                    getattr(response, "response", None)
                    or getattr(response, "result", None)
                    or {}
                )
    return results


def _is_transient_llm_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "503" in text or "high demand" in text or "unavailable" in text


def _should_try_next_model(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "resource_exhausted" in text
        or "quota exceeded" in text
        or "429" in text
        or "rate limit" in text
        or "too many requests" in text
        or "requests per minute" in text
        or "requests per day" in text
        or "tokens per minute" in text
        or "tokens per day" in text
        or "json mode cannot be combined with tool/function calling" in text
        or "reasoning_content" in text
        or ("model" in text and "404" in text)
        or ("model" in text and "not found" in text)
        or ("model" in text and "not supported" in text)
    )


def _user_generation_error(exc: Exception, fallback: str) -> str:
    text = str(exc).lower()
    if "json mode cannot be combined" in text or "reasoning_content" in text:
        return (
            "Configured LLM model is incompatible with the agent tool loop. "
            "Switch to a model that supports tool calling in this runner."
        )
    if _should_try_next_model(exc):
        return (
            "LLM provider quota or rate limits are exhausted for this project. "
            "Try again after the quota window resets or switch to a paid tier."
        )
    if _is_transient_llm_error(exc):
        return "Gemini is temporarily overloaded. Try again in a minute."
    return fallback


def _billing_tier() -> str:
    return "vertex" if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") == "true" else "free"


def _estimate_cost(prompt_tokens: int, output_tokens: int) -> float:
    input_per_million = 0.30
    output_per_million = 2.50
    return round(
        (prompt_tokens / 1_000_000 * input_per_million)
        + (output_tokens / 1_000_000 * output_per_million),
        8,
        )


_runner: GenerationRunner | None = None


def get_generation_runner() -> GenerationRunner:
    global _runner
    if _runner is None:
        _runner = AdkGenerationRunner()
    return _runner
