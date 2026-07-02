"""FastAPI application entry point.

Assembles middleware, routers, health probes, and startup/shutdown hooks.
Never log PHI. Always run behind nginx with TLS termination in production.
"""
import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.utils.logging import configure_logging
from app.utils.phi_scrub import sentry_before_send

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit_default])


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            before_send=sentry_before_send,
            traces_sample_rate=0.0,
            send_default_pii=False,
        )
    logger.info("app.startup", extra={"env": settings.app_env})
    yield
    await engine.dispose()
    logger.info("app.shutdown")


app = FastAPI(
    title="HIPAA Scheduler API",
    version="0.1.0",
    docs_url="/api/v1/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    openapi_url="/api/v1/openapi.json" if settings.app_env != "production" else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/v1/readyz", tags=["health"])
async def readyz() -> dict:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/api/v1/worker/health", tags=["health"])
async def worker_health() -> dict:
    """Liveness of the background worker + freshness of each scheduled job.

    Reads the heartbeat file the worker writes after every scheduler tick. Used
    for job-queue monitoring / alerting — an unhealthy result means the worker
    is hung, dead, or a job last failed.
    """
    from app.tasks import heartbeat

    return heartbeat.read_status()


from app.routers import (
    activity_log,
    api_keys,
    appointment_types,
    appointments,
    auth,
    availability,
    calendar_sync,
    consents,
    documents,
    insurance,
    intake_forms,
    notifications,
    offices,
    organizations,
    patients,
    patients_auth,
    providers,
    public_booking,
    public_confirm,
    reminders,
    reports,
    timeoff,
    users,
    waitlist,
    webhooks,
)
from app.routers.admin import audit_search as admin_audit_search
from app.routers.admin import impersonate as admin_impersonate
from app.routers.admin import plans as admin_plans
from app.routers.admin import seats as admin_seats
from app.routers.admin import tenants as admin_tenants


API_V1 = "/api/v1"

# Auth (unauthenticated / bootstrap endpoints)
app.include_router(auth.router, prefix=API_V1)
app.include_router(patients_auth.router, prefix=API_V1)

# Staff self-service
app.include_router(organizations.router, prefix=API_V1)
app.include_router(users.router, prefix=API_V1)
app.include_router(offices.router, prefix=API_V1)
app.include_router(providers.router, prefix=API_V1)
app.include_router(appointment_types.router, prefix=API_V1)
app.include_router(availability.router, prefix=API_V1)
app.include_router(timeoff.router, prefix=API_V1)

# Scheduling + patients
app.include_router(patients.router, prefix=API_V1)
app.include_router(appointments.router, prefix=API_V1)
app.include_router(waitlist.router, prefix=API_V1)

# Patient data
app.include_router(intake_forms.router, prefix=API_V1)
app.include_router(consents.router, prefix=API_V1)
app.include_router(documents.router, prefix=API_V1)
app.include_router(insurance.router, prefix=API_V1)

# Ops surfaces
app.include_router(notifications.router, prefix=API_V1)
app.include_router(reminders.router, prefix=API_V1)
app.include_router(activity_log.router, prefix=API_V1)
app.include_router(reports.router, prefix=API_V1)

# Integrations
app.include_router(api_keys.router, prefix=API_V1)
app.include_router(webhooks.router, prefix=API_V1)
app.include_router(calendar_sync.router, prefix=API_V1)

# Public (unauthenticated) surfaces
app.include_router(public_booking.router, prefix=API_V1)
app.include_router(public_confirm.router, prefix=API_V1)

# Super-admin
app.include_router(admin_tenants.router, prefix=API_V1)
app.include_router(admin_plans.router, prefix=API_V1)
app.include_router(admin_seats.router, prefix=API_V1)
app.include_router(admin_audit_search.router, prefix=API_V1)
app.include_router(admin_impersonate.router, prefix=API_V1)
