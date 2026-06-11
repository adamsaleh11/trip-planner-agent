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
    google_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    google_maps_api_key: Optional[str] = None
    google_routes_api_key: Optional[str] = None

    # ADK itinerary generation. Free-tier budget: gemini-3.1-flash-lite has
    # 500 requests/day (the workhorse); the other Gemini flash models only
    # get 20/day, so they are last-resort only. llama-3.3-70b is excluded
    # everywhere: its 12k TPM cap rejects the large tool-result payloads
    # that need a fallback in the first place.
    agent_model: str = "gemini-3.1-flash-lite"
    agent_model_fallbacks: str = (
        "gemini-2.5-flash-lite,gemini-3.5-flash"
    )
    # Category agents are member-triggered and run five at a time, so they
    # prefer Groq Scout (generous request limits) and spill into the Gemini
    # daily budget only on failure.
    agent_category_model: str = "groq/meta-llama/llama-4-scout-17b-16e-instruct"
    agent_category_model_fallbacks: str = (
        "gemini-3.1-flash-lite,"
        "gemini-2.5-flash-lite"
    )
    agent_coordinator_model: str = "gemini-3.1-flash-lite"
    agent_coordinator_model_fallbacks: str = (
        "groq/meta-llama/llama-4-scout-17b-16e-instruct,"
        "gemini-2.5-flash-lite"
    )
    agent_coordinator_gemini_models: str = (
        "gemini-3.1-flash-lite,"
        "gemini-2.5-flash-lite,"
        "gemini-3.5-flash"
    )
    agent_coordinator_groq_models: str = (
        "groq/meta-llama/llama-4-scout-17b-16e-instruct"
    )

    # Full-itinerary runs per trip per UTC day; 0 disables the cap. Each run
    # costs ~15 Places Enterprise calls, so this is the main quota guard.
    trip_generation_daily_cap: int = 3
    google_genai_use_vertexai: Optional[bool] = None

    # Anonymous collective-memory sharing
    server_hmac_secret: Optional[str] = "local-dev-secret"
    memory_scrub_model: str = "gemini-3.1-flash-lite"
    memory_embedding_model: str = "gemini-embedding-001"
    memory_embedding_dims: int = 3072

    @property
    def agent_model_sequence(self) -> list[str]:
        return self._model_sequence(self.agent_model, self.agent_model_fallbacks)

    @property
    def agent_category_model_sequence(self) -> list[str]:
        return self._model_sequence(
            self.agent_category_model,
            self.agent_category_model_fallbacks,
        )

    @property
    def agent_coordinator_model_sequence(self) -> list[str]:
        return self._model_sequence(
            self.agent_coordinator_model,
            self.agent_coordinator_model_fallbacks,
        )

    def coordinator_sequence_for_provider(self, provider: str | None) -> list[str]:
        """Admin-chosen coordinator provider; None keeps the default sequence."""
        if provider == "groq":
            return self._split_models(self.agent_coordinator_groq_models)
        if provider == "gemini":
            return self._split_models(self.agent_coordinator_gemini_models)
        return self.agent_coordinator_model_sequence

    @staticmethod
    def _split_models(models: str) -> list[str]:
        return [model.strip() for model in models.split(",") if model.strip()]

    def _model_sequence(self, primary: str, fallbacks: str) -> list[str]:
        models = [primary]
        models.extend(
            model.strip()
            for model in fallbacks.split(",")
            if model.strip()
        )
        return list(dict.fromkeys(models))


@lru_cache
def get_settings() -> Settings:
    return Settings()
