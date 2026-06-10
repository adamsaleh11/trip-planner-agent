from app.models.preferences import GroupPreferencesEntry
from app.models.trip import Trip
from travel_agent.graph import build_trip_agent_graph


def build_root_agent(
    trip_context: Trip,
    group_preferences: list[GroupPreferencesEntry],
):
    """Build a fresh Phase 3 agent graph for one itinerary generation request."""
    return build_trip_agent_graph(trip_context, group_preferences)
