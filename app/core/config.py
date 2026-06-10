"""Application configuration loaded from the environment / ``.env``.

No secrets live in code. Gmail sender fields are reserved for T1.2 and are
optional here so the service boots without them.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ROOT_DIR / "travel_agent/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google Cloud / Firestore
    gcp_project: Optional[str] = None
    firebase_credentials_path: Optional[str] = None
    firestore_database: str = "(default)"

    # Gmail invite sender (OAuth refresh-token flow)
    gmail_client_id: Optional[str] = None
    gmail_client_secret: Optional[str] = None
    gmail_refresh_token: Optional[str] = None

    # Base URL used to build invite links
    frontend_url: str = "http://localhost:3000"

    # Google Places destination search
    google_maps_api_key: Optional[str] = None
    google_routes_api_key: Optional[str] = None

    # ADK itinerary generation
    agent_model: str = "gemini-2.5-flash"
    google_genai_use_vertexai: Optional[bool] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
