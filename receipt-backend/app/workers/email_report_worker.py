import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import get_service_client

log = logging.getLogger(__name__)


async def run_email_report_job() -> None:
    """Send the previous month's spending report to every opted-in user."""
    from app.services.report_service import generate_monthly_report
    from app.services.email_service import build_monthly_report_html, send_email

    log.info("Starting monthly email report job...")

    now = datetime.now(timezone.utc)
    if now.month == 1:
        prev_month = f"{now.year - 1}-12"
    else:
        prev_month = f"{now.year}-{now.month - 1:02d}"

    db = get_service_client()

    users = (
        db.table("profiles")
        .select("id, email, full_name")
        .eq("notify_reports", True)
        .neq("email", "")
        .execute()
    )

    sent = 0
    failed = 0

    for user in users.data or []:
        user_id = user["id"]
        email = user.get("email", "")
        name = user.get("full_name", "").split(" ")[0] or "there"

        if not email:
            continue

        try:
            report = await generate_monthly_report(db, user_id, prev_month)

            # Skip users with no receipts that month
            if report["summary"]["receipts_count"] == 0:
                log.info(f"[email-report] {user_id}: no receipts in {prev_month}, skipping")
                continue

            html = build_monthly_report_html(report, name)
            subject = f"Your Receipt report for {report['period']}"

            ok = await send_email(email, subject, html)
            if ok:
                sent += 1
                log.info(f"[email-report] {user_id}: sent to {email}")
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            log.error(f"[email-report] {user_id}: failed — {exc}")

    log.info(f"Monthly email report job done — sent={sent}, failed={failed}")


def setup_email_report_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Run on the configured day of month (default: 1st) at configured hour (default: 09:00)."""
    scheduler.add_job(
        run_email_report_job,
        "cron",
        day=settings.REPORT_CRON_DAY,
        hour=settings.REPORT_CRON_HOUR,
        id="email_report_worker",
        replace_existing=True,
    )
    log.info(
        f"Email report worker scheduled: day {settings.REPORT_CRON_DAY} "
        f"at {settings.REPORT_CRON_HOUR}:00"
    )
