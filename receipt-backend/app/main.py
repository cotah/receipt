import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI, Request, HTTPException
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
from app.api.v1 import receipts, products, prices, chat, alerts, reports, leaflets, users, admin, payments, deals, shopping_list, feedback

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
        log.info("All required API keys loaded")

    from app.workers.intelligence_worker import setup_intelligence_scheduler

    setup_leaflet_scheduler(scheduler)
    setup_alert_scheduler(scheduler)
    setup_price_scheduler(scheduler)
    setup_email_report_scheduler(scheduler)
    setup_intelligence_scheduler(scheduler)

    # Deals engine — every 2 days at 04:00 UTC (after scrapers)
    from app.workers.deals_worker import generate_all_deals, snapshot_prices_to_history

    async def _deals_and_snapshot():
        """Run deals engine + price snapshot (for Smart Timing)."""
        await snapshot_prices_to_history()
        await generate_all_deals()

    scheduler.add_job(
        _deals_and_snapshot,
        "cron",
        hour=4,
        minute=0,
        day="*/2",
        id="deals_engine",
        replace_existing=True,
    )
    log.info("Deals engine scheduled: every 2 days at 04:00 UTC")

    # Product enrichment — daily at 05:00 UTC (after scrapers + deals)
    from app.services.enrichment_service import run_full_enrichment

    scheduler.add_job(
        run_full_enrichment,
        "cron",
        hour=5,
        minute=0,
        id="product_enrichment",
        replace_existing=True,
    )
    log.info("Product enrichment scheduled: daily at 05:00 UTC")

    scheduler.start()
    log.info("Background workers started")

    # Fire scrapers on startup if DB is empty (after a short delay)
    asyncio.create_task(run_all_scrapers_startup())

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    log.info("Background workers stopped")


async def run_all_scrapers_startup():
    """Wait for app to initialise, then run scrapers if DB is empty."""
    await asyncio.sleep(10)
    try:
        from app.database import get_service_client
        from app.workers.leaflet_worker import (
            run_dunnes_scraper,
            run_supervalu_scraper,
            run_tesco_scraper,
        )

        db = get_service_client()
        prices_check = (
            db.table("collective_prices")
            .select("id", count="exact")
            .eq("source", "leaflet")
            .limit(1)
            .execute()
        )
        if (prices_check.count or 0) > 0:
            log.info("Startup: collective_prices has data — skipping scrapers")
            return

        log.info("Startup: collective_prices is empty — running all scrapers sequentially...")
        await run_dunnes_scraper()
        await run_supervalu_scraper()
        await run_tesco_scraper()
        log.info("Startup: all scrapers finished")
    except Exception as e:
        log.error(f"Startup scraper run failed: {e}")


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

# Rate limiting
from app.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

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
app.include_router(deals.router, prefix="/api/v1")
app.include_router(shopping_list.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")

# Admin panel static files
_admin_dir = Path(__file__).resolve().parent.parent / "admin"
if _admin_dir.is_dir():
    app.mount("/admin", StaticFiles(directory=str(_admin_dir), html=True), name="admin")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}


@app.post("/api/v1/debug/run-scrapers")
async def debug_run_scrapers(request: Request):
    """Force-run all scrapers — requires X-Admin-Key header."""
    _verify_admin_key(request)
    from app.workers.leaflet_worker import (
        run_supervalu_scraper,
        run_tesco_scraper,
        run_lidl_scraper,
        run_leaflet_job,
    )

    asyncio.create_task(run_supervalu_scraper())
    asyncio.create_task(run_tesco_scraper())
    asyncio.create_task(run_lidl_scraper())
    asyncio.create_task(run_leaflet_job())  # Aldi
    return {"status": "started", "scrapers": ["supervalu", "tesco", "lidl", "aldi"]}


@app.post("/api/v1/debug/generate-deals")
async def debug_generate_deals(request: Request):
    """Force-generate weekly deals — requires X-Admin-Key header."""
    _verify_admin_key(request)
    from app.workers.deals_worker import generate_all_deals

    asyncio.create_task(generate_all_deals())
    return {"status": "started", "message": "Deal generation triggered"}


@app.post("/api/v1/debug/categorize")
async def debug_categorize(request: Request):
    """Categorize all 'Other' products — requires X-Admin-Key header."""
    _verify_admin_key(request)
    from app.api.v1.prices import _run_categorization_batch

    async def _run_all():
        total = 0
        for _ in range(100):  # Max 100 batches (5000 products)
            count = await _run_categorization_batch(50)
            if count == 0:
                break
            total += count
        import logging
        logging.getLogger(__name__).info(f"Categorization complete: {total} products")

    asyncio.create_task(_run_all())
    return {"status": "started", "message": "Categorization running in background"}


@app.post("/api/v1/debug/embed-products")
async def debug_embed_products(request: Request):
    """Generate embeddings for all products — requires X-Admin-Key header."""
    _verify_admin_key(request)
    from app.services.embedding_service import run_full_embedding

    async def _run():
        total = await run_full_embedding()
        import logging
        logging.getLogger(__name__).info(f"Embedding complete: {total} products")

    asyncio.create_task(_run())
    return {"status": "started", "message": "Embedding generation running in background"}


@app.post("/api/v1/debug/run-enrichment")
async def debug_run_enrichment(request: Request):
    """Run product enrichment (barcode_catalog + Open Food Facts) — requires X-Admin-Key."""
    _verify_admin_key(request)
    from app.services.enrichment_service import run_full_enrichment

    result = await run_full_enrichment()
    return {"status": "done", **result}


@app.post("/api/v1/debug/import-barcodes")
async def debug_import_barcodes(request: Request):
    """ONE-TIME: Import barcodes from JSON body into barcode_catalog. Remove after use."""
    _verify_admin_key(request)
    from app.database import get_service_client as _get_db
    from app.utils.text_utils import generate_product_key

    body = await request.json()
    items = body.get("items", [])
    db = _get_db()
    saved = 0

    for item in items:
        try:
            barcode = str(item.get("barcode", "")).strip()
            name = item.get("product_name", "").strip()
            if not barcode or not name or len(barcode) < 8:
                continue

            db.table("barcode_catalog").upsert({
                "barcode": barcode,
                "product_name": name,
                "product_key": generate_product_key(name),
                "brand": item.get("brand", ""),
                "category": "Other",
                "package_size": str(item.get("package_size", "")),
                "image_url": "",
                "store_name": None,
                "last_seen": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
            }, on_conflict="barcode").execute()
            saved += 1
        except Exception as e:
            pass

    return {"status": "done", "received": len(items), "saved": saved}


def _verify_admin_key(request: Request):
    """Check X-Admin-Key header matches ADMIN_KEY env var."""
    if not settings.ADMIN_KEY:
        return  # No key configured = open (dev mode)
    key = request.headers.get("X-Admin-Key", "")
    if key != settings.ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")
