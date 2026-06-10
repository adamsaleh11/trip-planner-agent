from app.models.preferences import GroupPreferencesEntry
from app.models.trip import Trip
from travel_agent.graph import build_category_agent
from travel_agent.schemas import Category


def build_location_research_agent(
    category: Category,
    trip_context: Trip,
    group_preferences: list[GroupPreferencesEntry],
):
    """Compatibility wrapper for category-specific location research agents."""
    return build_category_agent(category, trip_context, group_preferences)
