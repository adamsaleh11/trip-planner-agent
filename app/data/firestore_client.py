"""Single Firestore client factory.

The only place a raw ``google-cloud-firestore`` client is constructed. Built
from settings; credentials come from the environment / service account, never
from code.
"""

from app.core.config import get_settings


def build_client():
    from google.cloud import firestore

    settings = get_settings()
    return firestore.Client(
        project=settings.gcp_project,
        database=settings.firestore_database,
    )
