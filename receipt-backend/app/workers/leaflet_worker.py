import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from app.config import settings
from app.database import get_service_client
from app.utils.text_utils import generate_product_key

log = logging.getLogger(__name__)

PAGE_SIZE = 30
REQUEST_DELAY = 3  # seconds between requests

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IE,en-GB;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
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
            if session_resp.status_code == 403:
                log.warning(
                    "%s: 403 Forbidden on session — temporarily unavailable, "
                    "will retry next scheduled run",
                    label,
                )
                return
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
                if resp.status_code == 403:
                    log.warning(
                        "%s: 403 on page %d — stopping (temporarily blocked)",
                        label, page,
                    )
                    break
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
# Lidl Ireland (Schwarz API) scraper
# ---------------------------------------------------------------------------

LIDL_FLYER_API = (
    "https://endpoints.leaflets.schwarz/v4/flyer"
)

_MONTH_NAMES = [
    "", "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


def _lidl_flyer_slug(today: datetime | None = None) -> str:
    """Build the Lidl flyer slug for the current week.

    Format: ``from-thu-DD-MM-to-wed-DD-MM-{month(s)}``
    The Thursday is the *next* Thursday from ``today`` (inclusive).
    Wednesday is 6 days after that Thursday.
    If the two dates span different months the suffix is
    ``{month1}-to-{month2}``, otherwise just ``{month}``.
    """
    if today is None:
        today = datetime.now(timezone.utc)

    # Next Thursday (weekday 3). If today is Thursday, use today.
    days_ahead = (3 - today.weekday()) % 7
    if days_ahead == 0 and today.hour >= 12:
        # If it's already Thursday afternoon, still use this Thursday
        pass
    thu = today + timedelta(days=days_ahead)
    wed = thu + timedelta(days=6)

    thu_dd = f"{thu.day:02d}"
    thu_mm = f"{thu.month:02d}"
    wed_dd = f"{wed.day:02d}"
    wed_mm = f"{wed.month:02d}"

    if thu.month == wed.month:
        suffix = _MONTH_NAMES[thu.month]
    else:
        suffix = f"{_MONTH_NAMES[thu.month]}-to-{_MONTH_NAMES[wed.month]}"

    return f"from-thu-{thu_dd}-{thu_mm}-to-wed-{wed_dd}-{wed_mm}-{suffix}"


async def scrape_lidl_leaflet() -> None:
    """Fetch the current Lidl Ireland weekly flyer and save products."""
    db = get_service_client()
    now = datetime.now(timezone.utc)
    default_expires = now + timedelta(days=7)
    total_saved = 0
    errors = 0

    slug = _lidl_flyer_slug(now)
    log.info("Lidl scraper: slug=%s", slug)

    # Clean expired Lidl entries
    db.table("collective_prices").delete().eq(
        "store_name", "Lidl",
    ).eq("source", "leaflet").lt(
        "expires_at", now.isoformat(),
    ).execute()
    log.info("Lidl scraper: expired entries removed")

    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers=BROWSER_HEADERS,
    ) as client:
        params = {
            "flyer_identifier": slug,
            "region_id": "0",
            "region_code": "0",
        }
        try:
            resp = await client.get(LIDL_FLYER_API, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.error("Lidl scraper: API request failed: %s", e)
            return

        # Flyer-level endDate for default expiry
        flyer_end = default_expires
        flyer_info = data if isinstance(data, dict) else {}
        end_str = flyer_info.get("endDate") or flyer_info.get("end_date")
        if end_str:
            try:
                dt = dateutil_parser.isoparse(end_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                flyer_end = dt
            except (ValueError, TypeError):
                pass

        # Products can be nested in various structures
        products: list[dict] = []
        if isinstance(data, list):
            products = data
        elif isinstance(data, dict):
            # Try common keys
            for key in ("products", "items", "pages"):
                items = data.get(key)
                if items and isinstance(items, list):
                    # "pages" may contain nested product lists
                    if key == "pages":
                        for page in items:
                            if isinstance(page, dict):
                                page_items = page.get("products") or page.get("items") or []
                                products.extend(page_items)
                            elif isinstance(page, list):
                                products.extend(page)
                    else:
                        products = items
                    break

        log.info("Lidl scraper: found %d products", len(products))

        for item in products:
            try:
                name = item.get("title") or item.get("name")
                price = item.get("price") or item.get("priceNumeric")
                if not name or price is None:
                    continue

                price = float(price)
                category = item.get("categoryPrimary") or "Other"

                # Item-level or flyer-level expiry
                item_expires = flyer_end
                item_flyer = item.get("flyer") or {}
                item_end = item_flyer.get("endDate") or item_flyer.get("end_date")
                if item_end:
                    try:
                        dt = dateutil_parser.isoparse(item_end)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        item_expires = dt
                    except (ValueError, TypeError):
                        pass

                product_key = generate_product_key(name)

                db.table("collective_prices").insert({
                    "product_key": product_key,
                    "product_name": name,
                    "category": category,
                    "store_name": "Lidl",
                    "unit_price": price,
                    "is_on_offer": True,
                    "source": "leaflet",
                    "observed_at": now.isoformat(),
                    "expires_at": item_expires.isoformat(),
                }).execute()
                total_saved += 1
            except Exception as e:
                errors += 1
                log.warning("Lidl scraper: item error: %s", e)

    log.info(
        "Lidl scraper: finished — %d items saved, %d errors",
        total_saved,
        errors,
    )


# ---------------------------------------------------------------------------
# Tesco Ireland (SSR HTML) scraper
# ---------------------------------------------------------------------------

TESCO_BASE_URL = (
    "https://www.tesco.ie/groceries/en-IE/promotions/all"
)
TESCO_SESSION_URL = "https://www.tesco.ie/groceries/en-IE/"
TESCO_PAGE_SIZE = 24
TESCO_REQUEST_DELAY = 2  # seconds between pages

_TESCO_TOTAL_RE = re.compile(r"of\s+([\d,]+)\s+results?", re.IGNORECASE)
_TESCO_PRICE_RE = re.compile(r"[\d]+[.,]\d{2}")


def _parse_tesco_price(text: str) -> float | None:
    """Extract the first decimal price from a text string."""
    m = _TESCO_PRICE_RE.search(text.replace(",", "."))
    if m:
        try:
            return float(m.group())
        except ValueError:
            pass
    return None


async def scrape_tesco_promotions() -> None:
    """Scrape Tesco Ireland promotions from SSR HTML pages."""
    db = get_service_client()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)
    total_saved = 0
    errors = 0

    log.info("Tesco scraper: starting...")

    # 1. Clean expired entries
    db.table("collective_prices").delete().eq(
        "store_name", "Tesco",
    ).eq("source", "leaflet").lt(
        "expires_at", now.isoformat(),
    ).execute()
    log.info("Tesco scraper: expired entries removed")

    # 2. Session with cookies
    tesco_headers = {
        **BROWSER_HEADERS,
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Referer": "https://www.tesco.ie/",
        "Origin": "https://www.tesco.ie",
    }
    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers=tesco_headers,
    ) as client:
        try:
            session_resp = await client.get(TESCO_SESSION_URL)
            session_resp.raise_for_status()
            log.info(
                "Tesco scraper: session established (%d cookies)",
                len(client.cookies),
            )
        except Exception as e:
            log.error("Tesco scraper: session failed: %s", e)
            return

        # 3. Discover total pages from first page
        total_pages = 1
        page = 1

        while page <= total_pages:
            params = {
                "sortBy": "relevance",
                "page": page,
                "count": TESCO_PAGE_SIZE,
            }
            try:
                resp = await client.get(TESCO_BASE_URL, params=params)
                resp.raise_for_status()
                html = resp.text
            except Exception as e:
                errors += 1
                log.warning("Tesco scraper: page %d failed (%s)", page, e)
                await asyncio.sleep(TESCO_REQUEST_DELAY)
                page += 1
                continue

            soup = BeautifulSoup(html, "html.parser")

            # Discover total on first page
            if page == 1:
                results_text = soup.get_text()
                m = _TESCO_TOTAL_RE.search(results_text)
                if m:
                    total_items_count = int(m.group(1).replace(",", ""))
                    total_pages = (
                        total_items_count + TESCO_PAGE_SIZE - 1
                    ) // TESCO_PAGE_SIZE
                    log.info(
                        "Tesco scraper: %d products across %d pages",
                        total_items_count,
                        total_pages,
                    )

            # 4. Extract products
            product_links = soup.select(
                "a[href*='/groceries/en-IE/products/']"
            )
            for link in product_links:
                try:
                    name = link.get_text(strip=True)
                    if not name:
                        continue

                    # Walk up to the product tile container
                    container = link
                    for _ in range(8):
                        if container.parent is None:
                            break
                        container = container.parent
                        # Check if we've found a reasonable container
                        price_el = container.select_one(
                            "[class*='product-tile-price__text'],"
                            "[class*='price-text'],"
                            "[class*='value']"
                        )
                        if price_el:
                            break

                    # Price
                    price = None
                    price_el = container.select_one(
                        "[class*='product-tile-price__text'],"
                        "[class*='price-text'],"
                        "[class*='price-per-sellable-unit']"
                    )
                    if price_el:
                        price = _parse_tesco_price(price_el.get_text())

                    if price is None:
                        # Try any text with € in the container
                        for el in container.find_all(
                            string=re.compile(r"€")
                        ):
                            price = _parse_tesco_price(str(el))
                            if price is not None:
                                break

                    if price is None:
                        continue

                    # Promotion text
                    promo_el = container.select_one(
                        "[class*='value-bar__content-text'],"
                        "[class*='promo'],"
                        "[class*='offer']"
                    )
                    is_on_offer = promo_el is not None

                    product_key = generate_product_key(name)

                    db.table("collective_prices").insert({
                        "product_key": product_key,
                        "product_name": name,
                        "category": "Other",
                        "store_name": "Tesco",
                        "unit_price": price,
                        "is_on_offer": is_on_offer,
                        "source": "leaflet",
                        "observed_at": now.isoformat(),
                        "expires_at": expires_at.isoformat(),
                    }).execute()
                    total_saved += 1

                except Exception as e:
                    errors += 1
                    log.warning(
                        "Tesco scraper: item error on page %d: %s",
                        page,
                        e,
                    )

            if page % 10 == 0:
                log.info(
                    "Tesco scraper: %d/%d pages (%d items saved)",
                    page,
                    total_pages,
                    total_saved,
                )

            await asyncio.sleep(TESCO_REQUEST_DELAY)
            page += 1

    log.info(
        "Tesco scraper: finished — %d items saved, %d errors",
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


async def run_lidl_scraper():
    """Run Lidl leaflet scraper standalone."""
    log.info("Starting Lidl leaflet scraper...")
    try:
        await scrape_lidl_leaflet()
    except Exception as e:
        log.error(f"Lidl scraper failed: {e}")


async def run_tesco_scraper():
    """Run Tesco promotions scraper standalone."""
    log.info("Starting Tesco promotions scraper...")
    try:
        await scrape_tesco_promotions()
    except Exception as e:
        log.error(f"Tesco scraper failed: {e}")


def setup_leaflet_scheduler(scheduler: AsyncIOScheduler):
    """Schedule leaflet and store scraper jobs."""
    # PDF leaflets (Aldi) — weekly on configured day
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

    # SuperValu — odd days at 06:00 (day 1,3,5,...,31)
    scheduler.add_job(
        run_supervalu_scraper,
        "cron",
        day="1-31/2",
        hour=6,
        minute=0,
        id="supervalu_scraper",
        replace_existing=True,
    )
    log.info("SuperValu scraper scheduled: odd days at 06:00")

    # Tesco — even days at 07:00 (day 2,4,6,...,30)
    scheduler.add_job(
        run_tesco_scraper,
        "cron",
        day="2-30/2",
        hour=7,
        minute=0,
        id="tesco_scraper",
        replace_existing=True,
    )
    log.info("Tesco scraper scheduled: even days at 07:00")

    # Lidl — every Thursday at 07:00
    scheduler.add_job(
        run_lidl_scraper,
        "cron",
        day_of_week="thu",
        hour=7,
        minute=0,
        id="lidl_scraper",
        replace_existing=True,
    )
    log.info("Lidl scraper scheduled: Thu at 07:00")
