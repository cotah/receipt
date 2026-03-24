import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import get_service_client
from app.config import settings

log = logging.getLogger(__name__)


async def run_leaflet_job():
    """Download and process weekly leaflets from Irish supermarkets."""
    log.info("Starting leaflet processing job...")
    try:
        from app.services.leaflet_service import fetch_and_process_leaflets
        db = get_service_client()
        await fetch_and_process_leaflets(db)
        log.info("Leaflet processing completed")
    except Exception as e:
        log.error(f"Leaflet job failed: {e}")


def setup_leaflet_scheduler(scheduler: AsyncIOScheduler):
    """Schedule leaflet fetch every Thursday at configured hour."""
    scheduler.add_job(
        run_leaflet_job,
        "cron",
        day_of_week=f"{settings.LEAFLET_CRON_DAY}",
        hour=settings.LEAFLET_CRON_HOUR,
        minute=0,
        id="leaflet_worker",
        replace_existing=True,
    )
    log.info(f"Leaflet worker scheduled: day={settings.LEAFLET_CRON_DAY}, hour={settings.LEAFLET_CRON_HOUR}")
