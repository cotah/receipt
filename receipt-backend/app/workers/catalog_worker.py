"""Full catalog scraper — Tesco Ireland via radeance/tesco-scraper on Apify.

Expands the product database from ~3,900 to 15,000+ products by scraping
the full Tesco IE grocery catalog (all categories). Runs weekly.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import get_service_client
from app.utils.text_utils import generate_product_key

log = logging.getLogger(__name__)

# All Tesco IE grocery category pages
TESCO_IE_CATEGORIES = [
    "https://www.tesco.ie/groceries/en-IE/shop/fresh-food/all",
    "https://www.tesco.ie/groceries/en-IE/shop/bakery/all",
    "https://www.tesco.ie/groceries/en-IE/shop/frozen-food/all",
    "https://www.tesco.ie/groceries/en-IE/shop/food-cupboard/all",
    "https://www.tesco.ie/groceries/en-IE/shop/drinks/all",
    "https://www.tesco.ie/groceries/en-IE/shop/health-and-beauty/all",
    "https://www.tesco.ie/groceries/en-IE/shop/household/all",
    "https://www.tesco.ie/groceries/en-IE/shop/pets/all",
    "https://www.tesco.ie/groceries/en-IE/shop/baby/all",
]

# Multibuy detection
_MULTIBUY_RE = re.compile(
    r"(?:any\s+)?(\d+)\s+for\s+[€£]?([\d]+\.?\d*)",
    re.IGNORECASE,
)


def _clean_gtin(gtin: str | None) -> str | None:
    """Clean GTIN/EAN barcode — strip padding zeros, validate."""
    if not gtin:
        return None
    gtin = gtin.strip()
    if not gtin.isdigit():
        return None
    # Strip leading zeros but keep at least 8 digits (EAN-8)
    stripped = gtin.lstrip("0")
    if len(stripped) < 8:
        # Restore enough leading zeros to make it 8 digits
        stripped = gtin[-(max(8, len(stripped))):]
    if len(stripped) < 8:
        return None
    return stripped


def _map_category(item: dict) -> str:
    """Map Tesco category hierarchy to SmartDocket categories."""
    main = (item.get("main_category") or "").strip()
    sub = (item.get("sub_category") or "").strip()

    category_map = {
        "Fresh Food": "Fresh Food",
        "Bakery": "Bakery",
        "Frozen Food": "Frozen",
        "Food Cupboard": "Pantry",
        "Drinks": "Drinks",
        "Health and Beauty": "Health & Beauty",
        "Household": "Household",
        "Pets": "Pets",
        "Baby": "Baby",
    }

    # Try main category first, then sub
    if main in category_map:
        return category_map[main]
    for key, val in category_map.items():
        if key.lower() in main.lower():
            return val
    return sub or main or "Other"


def save_tesco_catalog_items(db, items: list) -> dict:
    """Save items from radeance/tesco-scraper into collective_prices + barcode_catalog.

    Returns: {"products_saved": int, "barcodes_saved": int, "errors": int}
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=14)  # Catalog prices valid 2 weeks
    products_saved = 0
    barcodes_saved = 0
    errors = 0

    for item in items:
        try:
            name = item.get("name")
            price = item.get("price")
            if not name or price is None:
                continue

            price = float(price)
            if price <= 0 or price > 500:
                continue  # Skip invalid prices

            # Handle promotion / multi-buy
            promo = item.get("promotion")
            is_on_offer = bool(promo)
            promotion_text = None

            if promo and isinstance(promo, dict):
                promotion_text = promo.get("offerText") or promo.get("description")
            elif promo and isinstance(promo, str):
                promotion_text = promo

            # Multi-buy correction
            if promotion_text:
                multibuy = _MULTIBUY_RE.search(promotion_text)
                if multibuy:
                    deal_count = int(multibuy.group(1))
                    deal_total = float(multibuy.group(2))
                    if abs(price - deal_total) < 0.05 and deal_count > 1:
                        price = round(deal_total / deal_count, 2)

            product_key = generate_product_key(name)
            category = _map_category(item)
            brand = item.get("brand_name") or ""
            gtin = _clean_gtin(item.get("gtin"))
            unit = item.get("unit")
            image_url = item.get("image_url")
            in_stock = item.get("in_stock", True)

            # --- Save to collective_prices ---
            upsert_data = {
                "product_key": product_key,
                "product_name": name,
                "category": category,
                "store_name": "Tesco",
                "unit_price": price,
                "is_on_offer": is_on_offer,
                "source": "leaflet",  # Keep compatible with existing source enum
                "observed_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
            }

            db.table("collective_prices").upsert(
                upsert_data,
                on_conflict="product_key,store_name,source",
            ).execute()
            products_saved += 1

            # --- Save barcode if available ---
            if gtin:
                try:
                    db.table("barcode_catalog").upsert(
                        {
                            "barcode": gtin,
                            "product_name": name,
                            "product_key": product_key,
                            "brand": brand,
                            "category": category,
                            "package_size": item.get("netContents") or "",
                            "image_url": image_url or "",
                            "store_name": "Tesco",
                            "last_seen": now.isoformat(),
                        },
                        on_conflict="barcode",
                    ).execute()
                    barcodes_saved += 1
                except Exception as e:
                    # barcode_catalog table might not exist yet — skip silently
                    if barcodes_saved == 0 and errors == 0:
                        log.warning("barcode_catalog upsert failed (table may not exist): %s", e)

        except Exception as e:
            errors += 1
            if errors <= 5:
                log.warning("save_tesco_catalog: item error: %s", e)

    log.info(
        "save_tesco_catalog: %d products, %d barcodes saved (%d errors) from %d items",
        products_saved, barcodes_saved, errors, len(items),
    )
    return {
        "products_saved": products_saved,
        "barcodes_saved": barcodes_saved,
        "errors": errors,
    }


async def run_tesco_catalog_scraper(
    max_products: int = 20000,
    categories: list[str] | None = None,
) -> dict:
    """Run full Tesco IE catalog scrape via Apify.

    Returns summary dict with counts.
    """
    token = settings.APIFY_API_TOKEN
    actor_id = settings.APIFY_ACTOR_TESCO_CATALOG
    if not token or not actor_id:
        log.error("Catalog: APIFY_API_TOKEN or APIFY_ACTOR_TESCO_CATALOG not set")
        return {"error": "Not configured", "products_saved": 0}

    urls = categories or TESCO_IE_CATEGORIES
    log.info("Tesco catalog: starting scrape of %d categories (max %d products)...", len(urls), max_products)

    run_input = {
        "urls": urls,
        "countryCode": "IE",
        "maxProducts": max_products,
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            # --- Check for recent dataset we can reuse (last 48h) ---
            reuse_items = await _check_recent_dataset(client, token, actor_id, max_age_hours=48)
            if reuse_items:
                log.info("Tesco catalog: reusing recent dataset (%d items)", len(reuse_items))
                db = get_service_client()
                result = save_tesco_catalog_items(db, reuse_items)
                result["source"] = "reused_dataset"
                return result

            # --- Start new run ---
            log.info("Tesco catalog: starting new Apify run...")
            run_resp = await client.post(
                f"https://api.apify.com/v2/acts/{actor_id}/runs",
                params={"token": token},
                json=run_input,
            )

            if run_resp.status_code not in (200, 201):
                log.error("Tesco catalog: Apify start failed (%d)", run_resp.status_code)
                return {"error": f"Apify start failed: {run_resp.status_code}", "products_saved": 0}

            run_data = run_resp.json().get("data", {})
            run_id = run_data.get("id")
            dataset_id = run_data.get("defaultDatasetId")
            log.info("Tesco catalog: run started (id=%s, dataset=%s)", run_id, dataset_id)

            # --- Poll until complete ---
            items = await _poll_and_fetch(client, token, actor_id, run_id, dataset_id)
            if not items:
                log.warning("Tesco catalog: Apify returned 0 items")
                return {"error": "No items returned", "products_saved": 0}

            log.info("Tesco catalog: Apify returned %d items — saving...", len(items))
            db = get_service_client()
            result = save_tesco_catalog_items(db, items)
            result["source"] = "new_run"
            result["apify_run_id"] = run_id
            return result

    except Exception as e:
        log.error("Tesco catalog scraper failed: %s", e)
        return {"error": str(e), "products_saved": 0}


async def _check_recent_dataset(
    client: httpx.AsyncClient, token: str, actor_id: str, max_age_hours: int = 48,
) -> list[dict] | None:
    """Check if there's a recent successful dataset we can reuse."""
    try:
        runs_resp = await client.get(
            f"https://api.apify.com/v2/acts/{actor_id}/runs",
            params={"token": token, "limit": 5, "desc": "true"},
        )
        if runs_resp.status_code != 200:
            return None

        for run in runs_resp.json().get("data", {}).get("items", []):
            if run.get("status") != "SUCCEEDED":
                continue
            ds_id = run.get("defaultDatasetId")
            finished = run.get("finishedAt", "")
            if not ds_id or not finished:
                continue

            # Check age
            try:
                fin_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
                age_h = (datetime.now(timezone.utc) - fin_dt).total_seconds() / 3600
                if age_h > max_age_hours:
                    continue
            except Exception:
                continue

            # Check item count
            ds_resp = await client.get(
                f"https://api.apify.com/v2/datasets/{ds_id}",
                params={"token": token},
            )
            if ds_resp.status_code != 200:
                continue
            item_count = ds_resp.json().get("data", {}).get("itemCount", 0)
            if item_count < 100:
                continue

            log.info("Tesco catalog: found recent dataset %s (%d items, %.1fh old)", ds_id, item_count, age_h)
            return await _fetch_all_items(client, token, ds_id)

    except Exception as e:
        log.warning("Tesco catalog: error checking recent datasets: %s", e)
    return None


async def _poll_and_fetch(
    client: httpx.AsyncClient, token: str, actor_id: str,
    run_id: str, dataset_id: str,
    timeout_secs: int = 3600, poll_interval: int = 45,
) -> list[dict]:
    """Poll Apify run until complete, then fetch all dataset items."""
    elapsed = 0
    while elapsed < timeout_secs:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        try:
            resp = await client.get(
                f"https://api.apify.com/v2/actor-runs/{run_id}",
                params={"token": token},
            )
            if resp.status_code != 200:
                continue
            status = resp.json().get("data", {}).get("status", "RUNNING")
        except Exception:
            continue

        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            log.info("Tesco catalog: run finished status=%s after %ds", status, elapsed)
            if status != "SUCCEEDED":
                return []
            break

        if elapsed % 180 == 0:
            log.info("Tesco catalog: still running... (%ds elapsed)", elapsed)

    return await _fetch_all_items(client, token, dataset_id)


async def _fetch_all_items(
    client: httpx.AsyncClient, token: str, dataset_id: str,
) -> list[dict]:
    """Fetch all items from an Apify dataset (handles pagination)."""
    all_items = []
    offset = 0
    limit = 1000

    while True:
        try:
            resp = await client.get(
                f"https://api.apify.com/v2/datasets/{dataset_id}/items",
                params={"token": token, "limit": limit, "offset": offset, "format": "json"},
            )
            if resp.status_code != 200:
                log.warning("Tesco catalog: dataset fetch failed at offset %d", offset)
                break

            batch = resp.json()
            if not batch:
                break

            all_items.extend(batch)
            if len(batch) < limit:
                break  # Last page
            offset += limit
            log.info("Tesco catalog: fetched %d items so far...", len(all_items))
        except Exception as e:
            log.warning("Tesco catalog: fetch error at offset %d: %s", offset, e)
            break

    return all_items


def setup_catalog_scheduler(scheduler: AsyncIOScheduler):
    """Schedule the full catalog scrape — weekly on Sundays at 03:00."""
    async def _run():
        await run_tesco_catalog_scraper()

    scheduler.add_job(
        _run,
        "cron",
        day_of_week="sun",
        hour=3,
        minute=0,
        id="tesco_catalog_scraper",
        replace_existing=True,
    )
    log.info("Tesco catalog scraper scheduled: Sundays at 03:00")
