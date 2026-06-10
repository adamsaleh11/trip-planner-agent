import os
import sys

import requests
from dotenv import load_dotenv


load_dotenv("travel_agent/.env")

API_KEY = os.environ["GOOGLE_MAPS_API_KEY"]

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


def search_text(query: str, max_result_count: int = 11) -> dict:
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
    return response.json()


def main():
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        query = "steakhouses near Copacabana Rio de Janeiro Brazil"

    data = search_text(query)

    print(f"Query: {query}")
    print()

    for place in data.get("places", []):
        name = place.get("displayName", {}).get("text")
        address = place.get("formattedAddress")
        rating = place.get("rating")
        price = place.get("priceLevel")
        maps_uri = place.get("googleMapsUri")

        print(name)
        print(address)
        print("rating:", rating)
        print("price:", price)
        print(maps_uri)
        print()


if __name__ == "__main__":
    main()