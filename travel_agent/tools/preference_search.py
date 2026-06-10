import json
import os
from pathlib import Path

import vertexai
from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel


PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "trip-agent-498919")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
EMBEDDING_MODEL = "text-embedding-005"

INDEX_ENDPOINT_NAME = os.environ.get(
    "VECTOR_SEARCH_INDEX_ENDPOINT",
    "projects/572338604059/locations/us-central1/indexEndpoints/7275382679086825472",
)

DEPLOYED_INDEX_ID = os.environ.get(
    "VECTOR_SEARCH_DEPLOYED_INDEX_ID",
    "friend_preferences_deployed",
)

ROOT_DIR = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT_DIR / "data" / "friend_preferences.json"


def load_friend_preferences_by_id() -> dict:
    records = json.loads(SOURCE_PATH.read_text())
    return {record["friend_id"]: record for record in records}


def embed_query(query: str) -> list[float]:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)
    embedding = model.get_embeddings([query])[0]
    return embedding.values


def search_friend_preferences(query: str, num_neighbors: int = 11) -> dict:
    """Search friend preference memory using Vertex AI Vector Search.

    Args:
        query: Natural-language search query about friend preferences.
        num_neighbors: Number of matching friends to retrieve.

    Returns:
        A dictionary containing the query and matching friend preference records.
    """
    records_by_id = load_friend_preferences_by_id()
    query_embedding = embed_query(query)

    endpoint = aiplatform.MatchingEngineIndexEndpoint(
        index_endpoint_name=INDEX_ENDPOINT_NAME,
    )

    neighbor_groups = endpoint.find_neighbors(
        deployed_index_id=DEPLOYED_INDEX_ID,
        queries=[query_embedding],
        num_neighbors=num_neighbors,
    )

    results = []

    for neighbor in neighbor_groups[0]:
        record = records_by_id.get(neighbor.id)

        if not record:
            results.append(
                {
                    "friend_id": neighbor.id,
                    "score": neighbor.distance,
                    "text": None,
                    "metadata": {},
                }
            )
            continue

        results.append(
            {
                "friend_id": record["friend_id"],
                "name": record["name"],
                "score": neighbor.distance,
                "text": record["text"],
                "metadata": record["metadata"],
            }
        )

    return {
        "query": query,
        "results": results,
    }