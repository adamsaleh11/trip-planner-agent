import json
import os
import sys
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

ROOT_DIR = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT_DIR / "data" / "friend_preferences.json"


def load_friend_preferences_by_id():
    records = json.loads(SOURCE_PATH.read_text())
    return {record["friend_id"]: record for record in records}


def embed_query(query):
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)
    return model.get_embeddings([query])[0].values


def main():
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        query = "Who likes nightlife, parties, and social late-night activities?"

    records_by_id = load_friend_preferences_by_id()
    query_embedding = embed_query(query)

    endpoint = aiplatform.MatchingEngineIndexEndpoint(
        index_endpoint_name=INDEX_ENDPOINT_NAME,
    )
    results = endpoint.find_neighbors(
        deployed_index_id=DEPLOYED_INDEX_ID,
        queries=[query_embedding],
        num_neighbors=11,
    )

    print(f"Query: {query}")
    print()

    for neighbor in results[0]:
        record = records_by_id.get(neighbor.id)
        if not record:
            print(f"- {neighbor.id} score={neighbor.distance}")
            continue

        print(f"- {record['name']} ({record['friend_id']}) score={neighbor.distance}")
        print(f"  {record['text']}")


if __name__ == "__main__":
    main()
