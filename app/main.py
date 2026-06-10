from fastapi import FastAPI

from app.api import health, invites, me, preferences, trips
from app.core.logging import RequestLoggingMiddleware, configure_logging


def create_app() -> FastAPI:
    """Application factory.

    Builds the FastAPI app with default production dependencies. Tests
    construct their own app and swap auth / data-layer dependencies via
    ``app.dependency_overrides``.
    """
    configure_logging()

    app = FastAPI(title="Trip Journal API")
    app.add_middleware(RequestLoggingMiddleware)

    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(trips.router)
    app.include_router(invites.router)
    app.include_router(preferences.router)

    return app


app = create_app()
