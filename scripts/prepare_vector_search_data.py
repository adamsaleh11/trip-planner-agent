import json
import os
from pathlib import Path

import vertexai
from vertexai.language_models import TextEmbeddingModel


PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "trip-agent-498919")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
EMBEDDING_MODEL = "text-embedding-005"

ROOT_DIR = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT_DIR / "data" / "friend_preferences.json"
OUTPUT_DIR = ROOT_DIR / "build" / "vector_search"
OUTPUT_PATH = OUTPUT_DIR / "friend_preferences.jsonl"


def load_friend_preferences():
    return json.loads(SOURCE_PATH.read_text())


def build_embedding_text(record):
    metadata = record["metadata"]

    return "\n".join(
        [
            f"Name: {record['name']}",
            f"Friend ID: {record['friend_id']}",
            f"Preference summary: {record['text']}",
            f"Diet: {metadata.get('diet', 'unknown')}",
            f"Budget style: {metadata.get('budget_style', 'unknown')}",
            f"Pace: {metadata.get('pace', 'unknown')}",
            f"Activity style: {', '.join(metadata.get('activity_style', []))}",
            f"Constraints: {', '.join(metadata.get('constraints', []))}",
        ]
    )


def main():
    vertexai.init(project=PROJECT_ID, location=LOCATION)

    records = load_friend_preferences()
    model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w") as output_file:
        for record in records:
            embedding_text = build_embedding_text(record)
            embedding = model.get_embeddings([embedding_text])[0]

            vector_search_record = {
                "id": record["friend_id"],
                "embedding": embedding.values,
                "restricts": [
                    {
                        "namespace": "diet",
                        "allow": [record["metadata"].get("diet", "unknown")],
                    },
                    {
                        "namespace": "pace",
                        "allow": [record["metadata"].get("pace", "unknown")],
                    },
                ],
                "crowding_tag": record["friend_id"],
            }

            output_file.write(json.dumps(vector_search_record) + "\n")

    print(f"Wrote {len(records)} embeddings to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()