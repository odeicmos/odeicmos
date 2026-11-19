"""FastAPI application entry point; readiness is intentionally conservative."""

from fastapi import FastAPI

from odei_api.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "ODEI Clinic Management OS API. This scaffold exposes process health only; "
            "authenticated business routes are not yet enabled."
        ),
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
    )

    @app.get("/health/live", tags=["health"])
    async def liveness() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    async def readiness() -> dict[str, str]:
        # Database, identity provider and secret manager checks will be added before
        # this endpoint is used as a production readiness signal.
        return {"status": "not_ready", "reason": "dependencies_not_configured"}

    return app


app = create_app()
