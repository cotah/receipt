import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import get_service_client
from app.utils.price_utils import get_ttl_days
from app.utils.text_utils import generate_product_key

log = logging.getLogger(__name__)

DUNNES_BASE_URL = (
    "https://storefrontgateway.dunnesstoresgrocery.com/api/stores/258"
    "/locations/5df95c07-402e-419a-a699-8b895311ac5a"
    "/aisle/page_promotion"
)
DUNNES_PAGE_SIZE = 30
DUNNES_TOTAL_PAGES = 215
DUNNES_REQUEST_DELAY = 1  # seconds between requests


async def scrape_dunnes_promotions() -> None:
    """Scrape all Dunnes Stores promotion pages and save to collective_prices."""
    db = get_service_client()
    now = datetime.now(timezone.utc)
    total_saved = 0
    errors = 0

    log.info("Dunnes scraper: starting (%d pages)...", DUNNES_TOTAL_PAGES)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for page in range(1, DUNNES_TOTAL_PAGES + 1):
            skip = (page - 1) * DUNNES_PAGE_SIZE
            params = {
                "page": page,
                "skip": skip,
                "pageSize": DUNNES_PAGE_SIZE,
            }

            try:
                resp = await client.get(DUNNES_BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                errors += 1
                log.warning("Dunnes scraper: page %d failed (%s)", page, e)
                await asyncio.sleep(DUNNES_REQUEST_DELAY)
                continue

            products = data if isinstance(data, list) else data.get("products", data.get("items", []))

            for item in products:
                try:
                    name = item.get("name")
                    price = item.get("priceNumeric")
                    if not name or price is None:
                        continue

                    promo_name = None
                    promotions = item.get("promotions")
                    if promotions and len(promotions) > 0:
                        promo_name = promotions[0].get("name")

                    categories = item.get("defaultCategory", [])
                    category = "Other"
                    if categories and len(categories) > 0:
                        category = categories[0].get("category", "Other")

                    product_key = generate_product_key(name)
                    ttl_days = get_ttl_days(category)

                    db.table("collective_prices").insert({
                        "product_key": product_key,
                        "product_name": name,
                        "category": category,
                        "store_name": "Dunnes",
                        "unit_price": float(price),
                        "is_on_offer": promo_name is not None,
                        "source": "leaflet",
                        "observed_at": now.isoformat(),
                        "expires_at": (now + timedelta(days=max(ttl_days, 7))).isoformat(),
                    }).execute()
                    total_saved += 1
                except Exception as e:
                    errors += 1
                    log.warning("Dunnes scraper: item parse error on page %d: %s", page, e)

            if page % 50 == 0:
                log.info("Dunnes scraper: %d/%d pages done (%d items saved)", page, DUNNES_TOTAL_PAGES, total_saved)

            await asyncio.sleep(DUNNES_REQUEST_DELAY)

    log.info(
        "Dunnes scraper: finished — %d items saved, %d errors",
        total_saved,
        errors,
    )


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

    # Dunnes API scraper (runs after PDF leaflets)
    try:
        await scrape_dunnes_promotions()
    except Exception as e:
        log.error(f"Dunnes scraper failed: {e}")


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
