import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dateutil import parser as dateutil_parser

from app.config import settings
from app.database import get_service_client
from app.utils.text_utils import generate_product_key

log = logging.getLogger(__name__)

PAGE_SIZE = 30
REQUEST_DELAY = 1  # seconds between requests

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IE,en;q=0.9",
}


# ---------------------------------------------------------------------------
# Mi9 store configurations
# ---------------------------------------------------------------------------


class Mi9Store(NamedTuple):
    store_name: str
    session_url: str
    api_base: str
    location_id: str | None  # None = discover at runtime
    total_pages: int
    referer: str
    origin: str


DUNNES = Mi9Store(
    store_name="Dunnes",
    session_url=(
        "https://www.dunnesstoresgrocery.com"
        "/sm/delivery/rsid/258/promotions"
    ),
    api_base=(
        "https://storefrontgateway.dunnesstoresgrocery.com"
        "/api/stores/258/locations"
    ),
    location_id="5df95c07-402e-419a-a699-8b895311ac5a",
    total_pages=215,
    referer=(
        "https://www.dunnesstoresgrocery.com"
        "/sm/delivery/rsid/258/promotions"
    ),
    origin="https://www.dunnesstoresgrocery.com",
)

SUPERVALU = Mi9Store(
    store_name="SuperValu",
    session_url=(
        "https://shop.supervalu.ie"
        "/sm/delivery/rsid/5550/promotions"
    ),
    api_base=(
        "https://storefrontgateway.supervalu.ie"
        "/api/stores/5550/locations"
    ),
    location_id=None,  # discovered from session response
    total_pages=121,
    referer=(
        "https://shop.supervalu.ie"
        "/sm/delivery/rsid/5550/promotions"
    ),
    origin="https://shop.supervalu.ie",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


_LOCATION_RE = re.compile(
    r"/locations/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


async def _discover_location_id(
    client: httpx.AsyncClient,
    store: Mi9Store,
) -> str | None:
    """Try to extract the Mi9 location UUID from the session page or its
    subsequent API calls.  Falls back to scraping the HTML body."""
    # The session page often redirects through URLs containing the location id
    for redirect in client.history:
        m = _LOCATION_RE.search(str(redirect.url))
        if m:
            return m.group(1)

    # Also check the final URL
    # (client.history only populated after a followed redirect chain)
    # Try fetching the store-info endpoint which usually contains it
    try:
        info_resp = await client.get(
            f"{store.api_base.rsplit('/locations', 1)[0]}/info",
        )
        if info_resp.status_code == 200:
            info = info_resp.json()
            loc_id = info.get("locationId") or info.get("location_id")
            if loc_id:
                return loc_id
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Generic Mi9 scraper
# ---------------------------------------------------------------------------


async def scrape_mi9_store(store: Mi9Store) -> None:
    """Scrape all promotion pages for a Mi9-based store."""
    db = get_service_client()
    now = datetime.now(timezone.utc)
    default_expires = now + timedelta(days=7)
    total_saved = 0
    errors = 0
    label = f"{store.store_name} scraper"

    log.info("%s: starting (%d pages)...", label, store.total_pages)

    # 1. Clean up expired entries
    db.table("collective_prices").delete().eq(
        "store_name", store.store_name,
    ).eq("source", "leaflet").lt(
        "expires_at", now.isoformat(),
    ).execute()
    log.info("%s: expired entries removed", label)

    # 2. Open session
    headers = {
        **BROWSER_HEADERS,
        "Referer": store.referer,
        "Origin": store.origin,
    }
    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers=headers,
    ) as client:
        try:
            session_resp = await client.get(store.session_url)
            session_resp.raise_for_status()
            log.info(
                "%s: session established (%d cookies)",
                label,
                len(client.cookies),
            )
        except Exception as e:
            log.error("%s: failed to get session cookies: %s", label, e)
            return

        # 3. Resolve location id
        location_id = store.location_id
        if location_id is None:
            location_id = await _discover_location_id(client, store)
            if location_id is None:
                log.error(
                    "%s: could not discover location_id — aborting", label
                )
                return
            log.info("%s: discovered location_id=%s", label, location_id)

        api_url = f"{store.api_base}/{location_id}/aisle/page_promotion"

        # 4. Iterate pages
        for page in range(1, store.total_pages + 1):
            skip = (page - 1) * PAGE_SIZE
            params = {"page": page, "skip": skip, "pageSize": PAGE_SIZE}

            try:
                resp = await client.get(api_url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                errors += 1
                log.warning("%s: page %d failed (%s)", label, page, e)
                await asyncio.sleep(REQUEST_DELAY)
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

                    # Expiry
                    expires_at = _parse_expires(item, default_expires)

                    product_key = generate_product_key(name)

                    db.table("collective_prices").insert({
                        "product_key": product_key,
                        "product_name": name,
                        "category": category,
                        "store_name": store.store_name,
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
                        "%s: item error on page %d: %s", label, page, e
                    )

            if page % 50 == 0:
                log.info(
                    "%s: %d/%d pages (%d items saved)",
                    label,
                    page,
                    store.total_pages,
                    total_saved,
                )

            await asyncio.sleep(REQUEST_DELAY)

    log.info(
        "%s: finished — %d items saved, %d errors",
        label,
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


async def run_dunnes_scraper():
    """Run Dunnes scraper standalone."""
    log.info("Starting Dunnes promotions scraper...")
    try:
        await scrape_mi9_store(DUNNES)
    except Exception as e:
        log.error(f"Dunnes scraper failed: {e}")


async def run_supervalu_scraper():
    """Run SuperValu scraper standalone."""
    log.info("Starting SuperValu promotions scraper...")
    try:
        await scrape_mi9_store(SUPERVALU)
    except Exception as e:
        log.error(f"SuperValu scraper failed: {e}")


def setup_leaflet_scheduler(scheduler: AsyncIOScheduler):
    """Schedule leaflet and Mi9 scraper jobs."""
    # PDF leaflets — weekly on configured day
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

    # Dunnes — odd days at 05:00 (day 1,3,5,...,31)
    scheduler.add_job(
        run_dunnes_scraper,
        "cron",
        day="1-31/2",
        hour=5,
        minute=0,
        id="dunnes_scraper",
        replace_existing=True,
    )
    log.info("Dunnes scraper scheduled: odd days at 05:00")

    # SuperValu — even days at 06:00 (day 2,4,6,...,30)
    scheduler.add_job(
        run_supervalu_scraper,
        "cron",
        day="2-30/2",
        hour=6,
        minute=0,
        id="supervalu_scraper",
        replace_existing=True,
    )
    log.info("SuperValu scraper scheduled: even days at 06:00")
