import logging
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
        environment=settings.ENVIRONMENT,
        send_default_pii=False,
    )
from fastapi.staticfiles import StaticFiles
from app.api.v1 import receipts, products, prices, chat, alerts, reports, leaflets, users, admin, payments

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Europe/Dublin")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.workers.leaflet_worker import setup_leaflet_scheduler
    from app.workers.alerts_worker import setup_alert_scheduler
    from app.workers.prices_worker import setup_price_scheduler
    from app.workers.email_report_worker import setup_email_report_scheduler

    # Verify critical API keys are set
    _missing = []
    if not settings.GOOGLE_API_KEY:
        _missing.append("GOOGLE_API_KEY")
    if not settings.OPENAI_API_KEY:
        _missing.append("OPENAI_API_KEY")
    if not settings.SUPABASE_URL:
        _missing.append("SUPABASE_URL")
    if not settings.SUPABASE_SERVICE_KEY:
        _missing.append("SUPABASE_SERVICE_KEY")
    if _missing:
        log.warning(f"MISSING ENV VARS: {', '.join(_missing)} — receipt processing will fail!")
    else:
        log.info(
            f"API keys loaded — GOOGLE_API_KEY={settings.GOOGLE_API_KEY[:8]}..., "
            f"OPENAI_API_KEY={settings.OPENAI_API_KEY[:8]}..."
        )

    setup_leaflet_scheduler(scheduler)
    setup_alert_scheduler(scheduler)
    setup_price_scheduler(scheduler)
    setup_email_report_scheduler(scheduler)
    scheduler.start()
    log.info("Background workers started")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    log.info("Background workers stopped")


app = FastAPI(
    title="SmartDocket API",
    description="Smart grocery spending intelligence for Ireland",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(receipts.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(prices.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(leaflets.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")

# Admin panel static files
_admin_dir = Path(__file__).resolve().parent.parent / "admin"
if _admin_dir.is_dir():
    app.mount("/admin", StaticFiles(directory=str(_admin_dir), html=True), name="admin")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}
