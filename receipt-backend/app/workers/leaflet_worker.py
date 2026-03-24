import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dateutil import parser as dateutil_parser

from app.config import settings
from app.database import get_service_client
from app.utils.text_utils import generate_product_key

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dunnes Stores promotion scraper
# ---------------------------------------------------------------------------

DUNNES_SESSION_URL = (
    "https://www.dunnesstoresgrocery.com/sm/delivery/rsid/258/promotions"
)
DUNNES_API_URL = (
    "https://storefrontgateway.dunnesstoresgrocery.com/api/stores/258"
    "/locations/5df95c07-402e-419a-a699-8b895311ac5a"
    "/aisle/page_promotion"
)
DUNNES_PAGE_SIZE = 30
DUNNES_TOTAL_PAGES = 215
DUNNES_REQUEST_DELAY = 1  # seconds between requests

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IE,en;q=0.9",
    "Referer": "https://www.dunnesstoresgrocery.com/sm/delivery/rsid/258/promotions",
    "Origin": "https://www.dunnesstoresgrocery.com",
}


def _parse_expires(item: dict, fallback: datetime) -> datetime:
    """Extract expiry from promotions[0].endDateUtc, or use fallback."""
    promotions = item.get("promotions")
    if promotions and len(promotions) > 0:
        end_str = promotions[0].get("endDateUtc")
        if end_str:
            try:
                dt = dateutil_parser.isoparse(end_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError):
                pass
    return fallback


async def scrape_dunnes_promotions() -> None:
    """Scrape all Dunnes Stores promotion pages and save to collective_prices."""
    db = get_service_client()
    now = datetime.now(timezone.utc)
    default_expires = now + timedelta(days=7)
    total_saved = 0
    errors = 0

    log.info("Dunnes scraper: starting (%d pages)...", DUNNES_TOTAL_PAGES)

    # 1. Clean up expired Dunnes leaflet entries
    db.table("collective_prices").delete().eq(
        "store_name", "Dunnes"
    ).eq("source", "leaflet").lt(
        "expires_at", now.isoformat()
    ).execute()
    log.info("Dunnes scraper: expired entries removed")

    # 2. Open session to get cookies
    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers=BROWSER_HEADERS,
    ) as client:
        try:
            session_resp = await client.get(DUNNES_SESSION_URL)
            session_resp.raise_for_status()
            log.info(
                "Dunnes scraper: session established (%d cookies)",
                len(client.cookies),
            )
        except Exception as e:
            log.error("Dunnes scraper: failed to get session cookies: %s", e)
            return

        # 3. Iterate all pages
        for page in range(1, DUNNES_TOTAL_PAGES + 1):
            skip = (page - 1) * DUNNES_PAGE_SIZE
            params = {
                "page": page,
                "skip": skip,
                "pageSize": DUNNES_PAGE_SIZE,
            }

            try:
                resp = await client.get(DUNNES_API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                errors += 1
                log.warning("Dunnes scraper: page %d failed (%s)", page, e)
                await asyncio.sleep(DUNNES_REQUEST_DELAY)
                continue

            products = (
                data
                if isinstance(data, list)
                else data.get("products", data.get("items", []))
            )

            for item in products:
                try:
                    name = item.get("name")
                    price = item.get("priceNumeric")
                    if not name or price is None:
                        continue

                    # Promotion info
                    promo_name = None
                    promotions = item.get("promotions")
                    if promotions and len(promotions) > 0:
                        promo_name = promotions[0].get("name")

                    # Category
                    categories = item.get("defaultCategory", [])
                    category = "Other"
                    if categories and len(categories) > 0:
                        category = categories[0].get("category", "Other")

                    # Expiry from endDateUtc
                    expires_at = _parse_expires(item, default_expires)

                    product_key = generate_product_key(name)

                    db.table("collective_prices").insert({
                        "product_key": product_key,
                        "product_name": name,
                        "category": category,
                        "store_name": "Dunnes",
                        "unit_price": float(price),
                        "is_on_offer": promo_name is not None,
                        "source": "leaflet",
                        "observed_at": now.isoformat(),
                        "expires_at": expires_at.isoformat(),
                    }).execute()
                    total_saved += 1
                except Exception as e:
                    errors += 1
                    log.warning(
                        "Dunnes scraper: item error on page %d: %s", page, e
                    )

            if page % 50 == 0:
                log.info(
                    "Dunnes scraper: %d/%d pages (%d items saved)",
                    page,
                    DUNNES_TOTAL_PAGES,
                    total_saved,
                )

            await asyncio.sleep(DUNNES_REQUEST_DELAY)

    log.info(
        "Dunnes scraper: finished — %d items saved, %d errors",
        total_saved,
        errors,
    )


# ---------------------------------------------------------------------------
# Leaflet jobs
# ---------------------------------------------------------------------------


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


async def run_dunnes_job():
    """Standalone Dunnes scraper job (runs on its own schedule)."""
    log.info("Starting Dunnes promotions scraper...")
    try:
        await scrape_dunnes_promotions()
    except Exception as e:
        log.error(f"Dunnes scraper failed: {e}")


def setup_leaflet_scheduler(scheduler: AsyncIOScheduler):
    """Schedule leaflet and Dunnes scraper jobs."""
    # PDF leaflets — weekly on Thursday
    scheduler.add_job(
        run_leaflet_job,
        "cron",
        day_of_week=f"{settings.LEAFLET_CRON_DAY}",
        hour=settings.LEAFLET_CRON_HOUR,
        minute=0,
        id="leaflet_worker",
        replace_existing=True,
    )
    log.info(
        "Leaflet worker scheduled: day=%s, hour=%s",
        settings.LEAFLET_CRON_DAY,
        settings.LEAFLET_CRON_HOUR,
    )

    # Dunnes promotions — Wednesday and Saturday at 06:00
    scheduler.add_job(
        run_dunnes_job,
        "cron",
        day_of_week="wed,sat",
        hour=6,
        minute=0,
        id="dunnes_scraper",
        replace_existing=True,
    )
    log.info("Dunnes scraper scheduled: Wed+Sat at 06:00")
