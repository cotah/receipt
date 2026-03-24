import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import get_service_client
from app.config import settings

log = logging.getLogger(__name__)


async def run_alert_job():
    """Generate restock and price drop alerts for all users."""
    log.info("Starting alert generation job...")
    from app.services.alert_service import generate_restock_alerts, generate_price_drop_alerts

    db = get_service_client()

    # Get all users with alerts enabled
    users = (
        db.table("profiles")
        .select("id")
        .eq("notify_alerts", True)
        .execute()
    )

    for user in users.data or []:
        user_id = user["id"]
        try:
            await generate_restock_alerts(db, user_id)
            await generate_price_drop_alerts(db, user_id)
        except Exception as e:
            log.error(f"Alert generation failed for user {user_id}: {e}")

    log.info(f"Alert job completed for {len(users.data or [])} users")


def setup_alert_scheduler(scheduler: AsyncIOScheduler):
    """Schedule alert generation at configured interval."""
    scheduler.add_job(
        run_alert_job,
        "interval",
        minutes=settings.ALERT_CHECK_INTERVAL_MINUTES,
        id="alerts_worker",
        replace_existing=True,
    )
    log.info(f"Alert worker scheduled: every {settings.ALERT_CHECK_INTERVAL_MINUTES} minutes")
