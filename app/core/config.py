"""Application configuration loaded from the environment / ``.env``.

No secrets live in code. Gmail sender fields are reserved for T1.2 and are
optional here so the service boots without them.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
