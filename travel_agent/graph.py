from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from google.adk.agents.llm_agent import Agent
from google.genai import types

from app.core.config import get_settings
from app.models.preferences import CATEGORIES, GroupPreferencesEntry
from app.models.trip import Trip
from travel_agent.schemas import Category, CategoryCandidateList, Itinerary
from travel_agent.tools.location_research import estimate_route_time, search_location_options


CATEGORY_ORDER: list[Category] = [
    "food_drink",
    "outdoors_scenic",
    "nightlife",
    "culture_local",
    "logistics",
]
MAX_PLACES_QUERIES_PER_CATEGORY = 3
MAX_PLACES_RESULTS_PER_QUERY = 11
MAX_ROUTE_ESTIMATES_PER_GENERATION = 8
CATEGORY_AGENT_MAX_OUTPUT_TOKENS = 2048
COORDINATOR_MAX_OUTPUT_TOKENS = 4096

CATEGORY_QUERY_HINTS: dict[Category, list[str]] = {
    "food_drink": ["restaurants", "cafes", "local drinks"],
    "outdoors_scenic": ["viewpoints", "parks", "scenic walks"],
    "nightlife": ["bars", "live music", "clubs"],
    "culture_local": ["markets", "museums", "neighborhoods"],
    "logistics": ["transit hubs", "walkable areas", "practical stops"],
}


def search_collective_memory(
    destination: str,
    category: str,
    query: str = "",
    limit: int = 5,
) -> dict:
    """T4.1 placeholder: no retrieval loop, no private data exposed."""
    return {
        "destination": destination,
        "category": category,
        "query": query,
        "limit": limit,
        "status": "stubbed",
        "results": [],
    }


@dataclass
class ToolCallBudget:
    places_queries_by_category: dict[str, int] = field(default_factory=dict)
    route_estimates: int = 0

    def record_places_query(self, category: str, count: int = 1) -> None:
        next_count = self.places_queries_by_category.get(category, 0) + count
        if next_count > MAX_PLACES_QUERIES_PER_CATEGORY:
            raise RuntimeError(
                f"Places query budget exceeded for {category}: "
                f"{next_count}/{MAX_PLACES_QUERIES_PER_CATEGORY}"
            )
        self.places_queries_by_category[category] = next_count

    def record_route_estimate(self, count: int = 1) -> None:
        next_count = self.route_estimates + count
        if next_count > MAX_ROUTE_ESTIMATES_PER_GENERATION:
            raise RuntimeError(
                "Route estimate budget exceeded: "
                f"{next_count}/{MAX_ROUTE_ESTIMATES_PER_GENERATION}"
            )
        self.route_estimates = next_count


def build_category_agent(
    category: Category,
    trip_context: Trip,
    group_preferences: list[GroupPreferencesEntry],
) -> Agent:
    if category not in CATEGORIES:
        raise ValueError(f"Unknown preference category: {category}")

    filled = [
        entry
        for entry in group_preferences
        if getattr(entry.preferences, category) is not None
    ]
    instruction = _category_instruction(category, trip_context, group_preferences, filled)
    tools = [search_location_options, search_collective_memory]
    if category == "logistics":
        tools.insert(1, estimate_route_time)

    return Agent(
        model=get_settings().agent_model,
        name=f"{category}_agent",
        description=f"Finds grounded {category} itinerary candidates for one trip.",
        instruction=instruction,
        tools=tools,
        output_schema=CategoryCandidateList,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=CATEGORY_AGENT_MAX_OUTPUT_TOKENS,
        ),
    )


def build_coordinator_agent(trip_context: Trip) -> Agent:
    return Agent(
        model=get_settings().agent_model,
        name="itinerary_coordinator_agent",
        description="Merges category candidate lists into a schema-valid itinerary.",
        instruction=_coordinator_instruction(trip_context),
        tools=[estimate_route_time],
        output_schema=Itinerary,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=COORDINATOR_MAX_OUTPUT_TOKENS,
        ),
    )


def build_trip_agent_graph(
    trip_context: Trip,
    group_preferences: list[GroupPreferencesEntry],
) -> dict[str, Agent]:
    agents = {
        category: build_category_agent(category, trip_context, group_preferences)
        for category in CATEGORY_ORDER
    }
    agents["coordinator"] = build_coordinator_agent(trip_context)
    return agents


def validate_itinerary_grounding(
    itinerary: Itinerary,
    captured_tool_results: list[dict[str, Any]],
) -> None:
    known_place_ids = _collect_place_ids(captured_tool_results)
    missing = [
        stop.placeId
        for day in itinerary.days
        for block in day.blocks
        for stop in block.stops
        if stop.placeId not in known_place_ids
    ]
    if missing:
        raise ValueError(
            "Itinerary contains placeIds not found in captured tool results: "
            + ", ".join(sorted(set(missing)))
        )


def expected_dates(trip_context: Trip) -> list[str]:
    start = date.fromisoformat(trip_context.startDate)
    end = date.fromisoformat(trip_context.endDate)
    if end < start:
        raise ValueError("Trip endDate cannot be before startDate")
    return [(start + timedelta(days=offset)).isoformat() for offset in range((end - start).days + 1)]


def _category_instruction(
    category: Category,
    trip_context: Trip,
    group_preferences: list[GroupPreferencesEntry],
    filled: list[GroupPreferencesEntry],
) -> str:
    trip_summary = _trip_summary(trip_context, len(group_preferences))
    hard_constraints = _hard_constraints(group_preferences)
    query_hints = ", ".join(CATEGORY_QUERY_HINTS[category])

    if filled:
        preference_block = _preference_block(category, filled)
        category_mode = (
            f"Members filled {category}. Use their structured chips and free-text wishlists. "
            "Items directly supported by these filled preferences must set suggested=false. "
            "If you pad thin preferences with your own best-fit idea, set suggested=true for that item."
        )
    else:
        preference_block = _other_filled_preferences(category, group_preferences)
        category_mode = (
            f"No member filled {category} preferences. Infer a best-fit {category} profile "
            "from the trip context and the other filled categories below. "
            "Use suggested as item-level provenance, not as a category-level flag."
        )

    return f"""
You are the {category} specialist for this one trip.

Trip context:
{trip_summary}

Hard constraints:
- Dietary restrictions and mobility notes are hard filters and are never preferences to balance.
- If a venue conflicts with a hard constraint, do not recommend it.
- If required data is missing, write "Not available" instead of inventing it.
{hard_constraints}

Category mode:
{category_mode}

Member preference context:
{preference_block}

Tool and cost rules:
- Use search_location_options for real venues only. Tune interests toward: {query_hints}.
- Make at most {MAX_PLACES_QUERIES_PER_CATEGORY} Places queries for this category.
- Request at most {MAX_PLACES_RESULTS_PER_QUERY} results per Places query.
- Use search_collective_memory once at most; it is currently a no-op slot for future traveler tips.
- Only the logistics specialist may call estimate_route_time.

Output rules:
- Return only the CategoryCandidateList schema, not prose.
- category must be "{category}".
- Every venue must come from search_location_options tool results.
- Include name, place_id, address, lat, lng, why_it_fits, time_of_day_fit, estimated_price_level, suggested.
- suggested is item-level provenance: set suggested=false only when the candidate directly traces to explicit current trip participant preferences; set suggested=true for generic, inferred, padding, or memory-inspired candidates that do not directly trace to those preferences.
""".strip()


def _coordinator_instruction(trip_context: Trip) -> str:
    dates = ", ".join(expected_dates(trip_context))
    lodging = trip_context.lodgingArea or "Not available"
    return f"""
You are the itinerary coordinator for this one trip.

Trip context:
{_trip_summary(trip_context, None)}
Itinerary dates: {dates}

Merge candidate lists from the five category specialists into the final Itinerary schema:
- days must cover exactly these dates: {dates}.
- Each day should use morning, afternoon, and evening blocks where candidates fit.
- Each stop must include time, placeId, name, address, lat, lng, category, transport, whyItFits, suggested, source, and manualPlanId when applicable.
- Preserve suggested from the category candidate. Do not relabel inferred items as user-requested.
- Use source="participant_preference" when suggested=false because a category candidate traces directly to participant preferences.
- Use source="ai_suggestion" when suggested=true.
- manual plans are concrete user-added commitments from the manualPlans input. Schedule each manual plan into the itinerary when possible.
- Manual plan stops must set suggested=false, source="manual_plan", and manualPlanId to the source plan id.
- Manual plans do not come from category agents. Do not use them to change category candidate provenance.
- If a manual plan cannot be scheduled because of date, location, or missing required information, add a manualPlanWarnings item with manualPlanId, activity, and a user-readable reason.
- Use estimate_route_time for lodging-to-first-stop and important stop-to-stop movements, with lodging origin "{lodging}".
- Route estimate budget: at most {MAX_ROUTE_ESTIMATES_PER_GENERATION} calls for the whole generation.
- If route data is missing or not worth spending budget, set transport.durationText to "Not available".
- Every placeId must have appeared in category agent tool results. Do not invent places.
- Dietary restrictions and mobility notes are hard filters. Do not schedule stops that violate them.
- If schema validation fails, repair the JSON once and return only the repaired schema.
""".strip()


def _trip_summary(trip_context: Trip, group_size: int | None) -> str:
    parts = [
        f"Destination: {trip_context.destination.text}",
        f"Dates: {trip_context.startDate} to {trip_context.endDate}",
        f"Lodging area: {trip_context.lodgingArea or 'Not available'}",
    ]
    if group_size is not None:
        parts.append(f"Group size: {group_size}")
    return "\n".join(f"- {part}" for part in parts)


def _preference_block(category: Category, entries: list[GroupPreferencesEntry]) -> str:
    return "\n".join(_format_member_category(entry, category) for entry in entries)


def _other_filled_preferences(
    empty_category: Category,
    entries: list[GroupPreferencesEntry],
) -> str:
    rows: list[str] = []
    for entry in entries:
        for category in CATEGORY_ORDER:
            if category == empty_category:
                continue
            preference = getattr(entry.preferences, category)
            if preference is not None:
                rows.append(_format_member_category(entry, category))
    return "\n".join(rows) if rows else "No other category preferences were filled."


def _hard_constraints(entries: list[GroupPreferencesEntry]) -> str:
    constraints: list[str] = []
    for entry in entries:
        food = entry.preferences.food_drink
        if food and food.dietaryRestrictions:
            restrictions = [item for item in food.dietaryRestrictions if item != "none"]
            if restrictions:
                constraints.append(
                    f"{_member_label(entry)} dietary restrictions: {', '.join(restrictions)}"
                )
        logistics = entry.preferences.logistics
        if logistics and logistics.mobilityNotes:
            constraints.append(
                f"{_member_label(entry)} mobility notes: {logistics.mobilityNotes}"
            )
    return "\n".join(f"- {constraint}" for constraint in constraints) or "- None provided."


def _format_member_category(entry: GroupPreferencesEntry, category: Category) -> str:
    preference = getattr(entry.preferences, category)
    payload = preference.model_dump(exclude_none=True) if preference is not None else {}
    return (
        f"- member={_member_label(entry)} category={category} "
        f"preferences={json.dumps(payload, sort_keys=True)}"
    )


def _member_label(entry: GroupPreferencesEntry) -> str:
    return entry.displayName or entry.participantId


def _collect_place_ids(results: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(results, dict):
        for key, value in results.items():
            if key in {"id", "place_id", "placeId"} and isinstance(value, str):
                found.add(value)
            else:
                found.update(_collect_place_ids(value))
    elif isinstance(results, list):
        for item in results:
            found.update(_collect_place_ids(item))
    return found
