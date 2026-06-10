from app.models.trip import Trip
from travel_agent.graph import build_coordinator_agent


def build_final_response_agent(trip_context: Trip):
    """Compatibility wrapper for the Phase 3 coordinator agent."""
    return build_coordinator_agent(trip_context)
