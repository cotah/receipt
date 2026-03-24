import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import get_service_client
from app.config import settings

log = logging.getLogger(__name__)


async def run_price_job():
    """Clean up expired prices and refresh materialized view."""
    log.info("Starting price cleanup job...")
    from app.services.price_service import cleanup_expired_prices

    db = get_service_client()

    try:
        deleted = await cleanup_expired_prices(db)
        log.info(f"Cleaned up {deleted} expired prices")
    except Exception as e:
        log.error(f"Price cleanup failed: {e}")

    # Refresh materialized view
    try:
        db.rpc("refresh_product_patterns", {}).execute()
        log.info("Refreshed user_product_patterns materialized view")
    except Exception as e:
        log.warning(f"Could not refresh materialized view (may not exist yet): {e}")


def setup_price_scheduler(scheduler: AsyncIOScheduler):
    """Schedule price cleanup at configured interval."""
    scheduler.add_job(
        run_price_job,
        "interval",
        hours=settings.PRICE_CLEANUP_INTERVAL_HOURS,
        id="prices_worker",
        replace_existing=True,
    )
    log.info(f"Price worker scheduled: every {settings.PRICE_CLEANUP_INTERVAL_HOURS} hours")
