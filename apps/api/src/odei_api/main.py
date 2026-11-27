"""FastAPI application with fail-closed identity and database readiness."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from pymongo import AsyncMongoClient

from odei_api.config import get_settings
from odei_api.security import check_identity_provider_ready
from odei_api.migrations.control_plane_indexes import CURRENT_SCHEMA_VERSION
from odei_api.routers.control_plane import router as control_plane_router
from odei_api.routers.patients import router as patients_router
from odei_api.routers.clinical import router as clinical_router
from odei_api.routers.pharmacy import router as pharmacy_router
from odei_api.routers.laboratory import router as laboratory_router
from odei_api.routers.immunization import router as immunization_router
from odei_api.routers.finance import router as finance_router
from odei_api.routers.procurement import router as procurement_router
from odei_api.routers.inpatient import router as inpatient_router
from odei_api.routers.insurance import router as insurance_router
from odei_api.routers.appointments import router as appointments_router
from odei_api.routers.accounting import router as accounting_router
from odei_api.routers.reception import router as reception_router
from odei_api.routers.workforce import router as workforce_router
from odei_api.routers.facility_ops import router as facility_ops_router
from odei_api.routers.safety import router as safety_router
from odei_api.routers.privacy import router as privacy_router
from odei_api.routers.sync import router as sync_router
from odei_api.routers.nursing import router as nursing_router
from odei_api.routers.emergency import router as emergency_router
from odei_api.routers.referrals import router as referrals_router
from odei_api.routers.procedures import router as procedures_router

logger = logging.getLogger(__name__)


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
            logger.exception("MongoDB startup connectivity check failed")
            await client.close()
    try:
        yield
    finally:
        if app.state.mongo_client is not None:
            await app.state.mongo_client.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name, version="0.5.0",
        description="ODEI Clinic OS API. Business routes require verified OIDC identity.",
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None, lifespan=lifespan,
    )

    @app.get("/health/live", tags=["health"])
    async def liveness() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    async def readiness(request: Request) -> dict[str, str]:
        if not request.app.state.mongo_ready:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"status": "not_ready", "reason": "mongodb_unavailable"},
            )
        try:
            await request.app.state.mongo_database.command("ping")
            migration = await request.app.state.mongo_database.schema_migrations.find_one({
                "_id": CURRENT_SCHEMA_VERSION, "status": "applied",
            })
        except Exception as exc:
            logger.exception("Database readiness dependency check failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"status": "not_ready", "reason": "database_dependency_check_failed"},
            ) from exc
        if migration is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"status": "not_ready", "reason": "schema_migrations_pending"},
            )
        try:
            await check_identity_provider_ready()
        except HTTPException as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"status": "not_ready", "reason": "identity_provider_unavailable_or_unconfigured"},
            ) from exc
        return {"status": "ready", "dependencies": "mongodb,schema_migrations,oidc_jwks"}

    app.include_router(control_plane_router, prefix=settings.api_prefix)
    app.include_router(patients_router, prefix=settings.api_prefix)
    app.include_router(clinical_router, prefix=settings.api_prefix)
    app.include_router(pharmacy_router, prefix=settings.api_prefix)
    app.include_router(laboratory_router, prefix=settings.api_prefix)
    app.include_router(immunization_router, prefix=settings.api_prefix)
    app.include_router(finance_router, prefix=settings.api_prefix)
    app.include_router(procurement_router, prefix=settings.api_prefix)
    app.include_router(inpatient_router, prefix=settings.api_prefix)
    app.include_router(insurance_router, prefix=settings.api_prefix)
    app.include_router(appointments_router, prefix=settings.api_prefix)
    app.include_router(accounting_router, prefix=settings.api_prefix)
    app.include_router(reception_router, prefix=settings.api_prefix)
    app.include_router(workforce_router, prefix=settings.api_prefix)
    app.include_router(facility_ops_router, prefix=settings.api_prefix)
    app.include_router(safety_router, prefix=settings.api_prefix)
    app.include_router(privacy_router, prefix=settings.api_prefix)
    app.include_router(sync_router, prefix=settings.api_prefix)
    app.include_router(nursing_router, prefix=settings.api_prefix)
    app.include_router(emergency_router, prefix=settings.api_prefix)
    app.include_router(referrals_router, prefix=settings.api_prefix)
    app.include_router(procedures_router, prefix=settings.api_prefix)
    return app


app = create_app()
