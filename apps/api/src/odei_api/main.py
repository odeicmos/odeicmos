"""FastAPI application with dependency-aware readiness checks."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from pymongo import AsyncMongoClient

from odei_api.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.mongo_client = None
    app.state.mongo_database = None
    app.state.mongo_ready = False
    if settings.mongodb_uri:
        client = AsyncMongoClient(
            settings.mongodb_uri.get_secret_value(),
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000,
            appname="odei-clinic-os-api",
        )
        try:
            await client.admin.command("ping")
            app.state.mongo_client = client
            app.state.mongo_database = client[settings.mongodb_database]
            app.state.mongo_ready = True
        except Exception:
            await client.close()
    try:
        yield
    finally:
        if app.state.mongo_client is not None:
            await app.state.mongo_client.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        description=(
            "ODEI Clinic Management OS API. This increment verifies MongoDB connectivity; "
            "authenticated business routes are not yet enabled."
        ),
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    @app.get("/health/live", tags=["health"])
    async def liveness() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    async def readiness(request: Request) -> dict[str, str]:
        if not request.app.state.mongo_ready:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"status": "not_ready", "reason": "mongodb_unavailable_or_unconfigured"},
            )
        return {"status": "ready", "dependencies": "mongodb"}

    return app


app = create_app()
