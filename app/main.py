import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import generation, health, invites, me, places, preferences, trips
from app.core.config import get_settings
from app.core.logging import RequestLoggingMiddleware, configure_logging


def create_app() -> FastAPI:
    """Application factory.

    Builds the FastAPI app with default production dependencies. Tests
    construct their own app and swap auth / data-layer dependencies via
    ``app.dependency_overrides``.
    """
    configure_logging()
    settings = get_settings()
    if settings.google_genai_use_vertexai is not None:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = (
            "true" if settings.google_genai_use_vertexai else "false"
        )
    allowed_origins = {
        settings.frontend_url.rstrip("/"),
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    }

    app = FastAPI(title="Trip Journal API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(allowed_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(trips.router)
    app.include_router(invites.router)
    app.include_router(places.router)
    app.include_router(preferences.router)
    app.include_router(generation.router)

    return app


app = create_app()
