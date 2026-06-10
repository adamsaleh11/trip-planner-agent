"""Seed clearly synthetic collective-memory tips for demos.

This script writes only anonymized, synthetic records. It does not read users,
trips, journal entries, or any private collections.
"""

from __future__ import annotations

from app.data.repository import get_repository
from app.services.collective_memory import COLLECTIVE_MEMORY_COLLECTION, LocalSharePipeline


SEED_ENTRIES = [
    ("lisbon", "food_drink", "places/lisbon-pastel", "Pastelaria Aurora", 5, "Synthetic travelers tip: go before 10 for warm custard tarts.", "small", 5),
    ("lisbon", "food_drink", "places/lisbon-seafood", "Mar Azul", 4, "Synthetic travelers tip: split seafood rice and book the early seating.", "small", 6),
    ("lisbon", "outdoors_scenic", "places/lisbon-miradouro", "Miradouro Alto", 5, "Synthetic travelers tip: sunset is crowded but the lower terrace stays calmer.", "small", 7),
    ("lisbon", "nightlife", "places/lisbon-fado", "Casa do Fado Claro", 4, "Synthetic travelers tip: the late set feels more local and less rushed.", "small", 8),
    ("lisbon", "culture_local", "places/lisbon-market", "Mercado do Bairro", 5, "Synthetic travelers tip: browse the tile stalls before lunch crowds arrive.", "small", 6),
    ("mexico-city", "food_drink", "places/cdmx-tacos", "Taqueria Jacaranda", 5, "Synthetic travelers tip: the al pastor line moves fast after 8 pm.", "small", 3),
    ("mexico-city", "food_drink", "places/cdmx-cafe", "Cafe Nube", 4, "Synthetic travelers tip: ask for the upstairs window table for a quiet reset.", "solo", 4),
    ("mexico-city", "outdoors_scenic", "places/cdmx-park", "Parque Verde", 4, "Synthetic travelers tip: Sunday morning has the best people-watching loop.", "small", 2),
    ("mexico-city", "culture_local", "places/cdmx-museum", "Museo Calle Norte", 5, "Synthetic travelers tip: start on the top floor and work down.", "large", 5),
    ("mexico-city", "nightlife", "places/cdmx-jazz", "Sotano Jazz", 5, "Synthetic travelers tip: reserve near the bar for the best sound.", "small", 9),
    ("montreal", "food_drink", "places/mtl-bagel", "Bagel Saint-Rue", 5, "Synthetic travelers tip: get one hot from the oven and walk the canal.", "solo", 10),
    ("montreal", "food_drink", "places/mtl-poutine", "Friterie du Coin", 4, "Synthetic travelers tip: one large is enough for two after a late show.", "small", 11),
    ("montreal", "outdoors_scenic", "places/mtl-lookout", "Belvedere Nord", 5, "Synthetic travelers tip: bring a layer; the overlook gets windy.", "small", 9),
    ("montreal", "culture_local", "places/mtl-market", "Marche des Ateliers", 4, "Synthetic travelers tip: the handmade paper stall is easy to miss.", "small", 8),
    ("montreal", "logistics", "places/mtl-metro", "Metro Central", 4, "Synthetic travelers tip: buy a day pass before hopping neighborhoods.", "large", 7),
]


def main() -> None:
    repo = get_repository()
    pipeline = LocalSharePipeline()
    for index, entry in enumerate(SEED_ENTRIES, start=1):
        destination, category, place_id, venue_name, rating, text, bucket, month = entry
        doc_id = f"synthetic-{destination}-{index:02d}"
        repo.set(
            COLLECTIVE_MEMORY_COLLECTION,
            doc_id,
            {
                "destination": destination,
                "category": category,
                "placeId": place_id,
                "venueName": venue_name,
                "rating": rating,
                "scrubbedText": text,
                "groupSizeBucket": bucket,
                "monthVisited": month,
                "embedding": pipeline.embed(f"{text} {venue_name} {destination} {category}"),
                "synthetic": True,
            },
        )
    print(f"Seeded {len(SEED_ENTRIES)} synthetic collective-memory entries.")


if __name__ == "__main__":
    main()
