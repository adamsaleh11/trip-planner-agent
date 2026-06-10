import os

import requests
from dotenv import load_dotenv


load_dotenv("travel_agent/.env")

API_KEY = os.environ["GOOGLE_MAPS_API_KEY"]

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

ROUTES_FIELD_MASK = ",".join(
    [
        "routes.duration",
        "routes.distanceMeters",
        "routes.polyline.encodedPolyline",
    ]
)

TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.rating",
        "places.userRatingCount",
        "places.priceLevel",
        "places.regularOpeningHours",
        "places.businessStatus",
        "places.types",
        "places.googleMapsUri",
    ]
)


def search_places_text(query: str, max_result_count: int = 11) -> list[dict]:
    response = requests.post(
        TEXT_SEARCH_URL,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": FIELD_MASK,
        },
        json={
            "textQuery": query,
            "maxResultCount": max_result_count,
            "languageCode": "en",
        },
        timeout=20,
    )

    response.raise_for_status()
    data = response.json()

    results = []

    for place in data.get("places", []):
        display_name = place.get("displayName", {})
        location = place.get("location", {})
        opening_hours = place.get("regularOpeningHours", {})

        results.append(
            {
                "id": place.get("id"),
                "name": display_name.get("text"),
                "address": place.get("formattedAddress"),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
                "rating": place.get("rating"),
                "user_rating_count": place.get("userRatingCount"),
                "price_level": place.get("priceLevel"),
                "business_status": place.get("businessStatus"),
                "types": place.get("types", []),
                "google_maps_uri": place.get("googleMapsUri"),
                "opening_hours": opening_hours.get("weekdayDescriptions", []),
            }
        )

    return results


def build_queries(destination: str, lodging_area: str, interests: list[str]) -> list[str]:
    queries = []

    for interest in interests:
        queries.append(f"{interest} near {lodging_area}, {destination}")

    return queries


def search_location_options(
    destination: str,
    lodging_area: str,
    interests: list[str],
    num_results: int = 11,
) -> dict:
    """Search real location options using Google Places Text Search.

    Args:
        destination: Destination city or region, such as "Rio de Janeiro, Brazil".
        lodging_area: Airbnb neighborhood, address, or nearest landmark.
        interests: Activity categories to research.
        num_results: Maximum number of results per interest query.

    Returns:
        A dictionary of grounded location results from Google Places.
    """
    queries = build_queries(destination, lodging_area, interests)
    grouped_results = []

    for query in queries:
        places = search_places_text(query, max_result_count=num_results)

        grouped_results.append(
            {
                "query": query,
                "places": places,
            }
        )

    return {
        "destination": destination,
        "lodging_area": lodging_area,
        "interests": interests,
        "status": "live",
        "source": "google_places_text_search",
        "results": grouped_results,
    }


def estimate_route_time(
    origin: str,
    destination: str,
    travel_mode: str = "TRANSIT",
) -> dict:
    """Estimate travel time between two places using Google Routes API.

    Args:
        origin: Starting address or area.
        destination: Destination address or place address.
        travel_mode: TRANSIT, WALK, DRIVE, or BICYCLE.

    Returns:
        Route duration and distance if available.
    """
    response = requests.post(
        ROUTES_URL,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": ROUTES_FIELD_MASK,
        },
        json={
            "origin": {
                "address": origin,
            },
            "destination": {
                "address": destination,
            },
            "travelMode": travel_mode,
            "languageCode": "en",
            "units": "METRIC",
        },
        timeout=20,
    )

    response.raise_for_status()
    data = response.json()
    routes = data.get("routes", [])

    if not routes:
        return {
            "origin": origin,
            "destination": destination,
            "travel_mode": travel_mode,
            "duration": "Not available",
            "distance_meters": None,
        }

    route = routes[0]

    return {
        "origin": origin,
        "destination": destination,
        "travel_mode": travel_mode,
        "duration": route.get("duration", "Not available"),
        "distance_meters": route.get("distanceMeters"),
    }
