"""FastAPI application with fail-closed identity and database readiness."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from pymongo import AsyncMongoClient
from odei_api.config import get_settings
from odei_api.routers.control_plane import router as control_plane_router
from odei_api.routers.patients import router as patients_router
from odei_api.routers.clinical import router as clinical_router
from odei_api.routers.pharmacy import router as pharmacy_router


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
        title=settings.app_name, version="0.3.0",
        description="ODEI Clinic OS control-plane API. Business routes require verified OIDC identity.",
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None, lifespan=lifespan,
    )

    @app.get("/health/live", tags=["health"])
    async def liveness() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    async def readiness(request: Request) -> dict[str, str]:
        identity_configured = all((settings.oidc_issuer, settings.oidc_audience, settings.oidc_jwks_url))
        if not request.app.state.mongo_ready or not identity_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"status": "not_ready", "reason": "mongodb_or_identity_provider_unavailable_or_unconfigured"},
            )
        return {"status": "ready", "dependencies": "mongodb"}

    app.include_router(control_plane_router, prefix=settings.api_prefix)
    app.include_router(patients_router, prefix=settings.api_prefix)
    app.include_router(clinical_router, prefix=settings.api_prefix)
    app.include_router(pharmacy_router, prefix=settings.api_prefix)
    return app


app = create_app()
