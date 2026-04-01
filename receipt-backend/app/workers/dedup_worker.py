"""Product deduplication worker.

Runs weekly to find and merge duplicate products in collective_prices.
Uses the order-independent generate_product_key to identify duplicates.

SAFE: When two entries have the same new_key + same store, keeps the cheapest.
Also updates all product_keys to the new sorted format.
"""
import logging
from collections import defaultdict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import get_service_client
from app.utils.text_utils import generate_product_key

log = logging.getLogger(__name__)


async def run_dedup_job() -> dict:
    """Scan collective_prices for duplicates and merge them."""
    log.info("Starting product deduplication scan...")

    db = get_service_client()

    # Fetch all products (paginate)
    all_products = []
    offset = 0
    batch_size = 1000
    while True:
        result = (
            db.table("collective_prices")
            .select("id, product_name, product_key, store_name, unit_price")
            .range(offset, offset + batch_size - 1)
            .execute()
        )
        if not result.data:
            break
        all_products.extend(result.data)
        if len(result.data) < batch_size:
            break
        offset += batch_size

    log.info("Dedup: scanned %d products", len(all_products))

    # 1. Update product_keys to new sorted format
    keys_updated = 0
    for p in all_products:
        new_key = generate_product_key(p["product_name"])
        if p["product_key"] != new_key:
            try:
                db.table("collective_prices").update(
                    {"product_key": new_key}
                ).eq("id", p["id"]).execute()
                keys_updated += 1
            except Exception as e:
                log.warning("Dedup: failed to update key for %s: %s", p["id"], e)

    # 2. Find duplicates: same new_key + same store = duplicate
    by_key_store = defaultdict(list)
    for p in all_products:
        new_key = generate_product_key(p["product_name"])
        by_key_store[(new_key, p["store_name"])].append(p)

    # 3. Merge duplicates — keep cheapest, remove extras
    merged = 0
    for (key, store), entries in by_key_store.items():
        if len(entries) <= 1:
            continue

        # Sort by price — keep the cheapest
        entries.sort(key=lambda x: float(x["unit_price"]))
        keep = entries[0]
        remove = entries[1:]

        for dup in remove:
            try:
                db.table("collective_prices").delete().eq("id", dup["id"]).execute()
                merged += 1
                log.info(
                    "Dedup: removed duplicate '%s' at %s (€%.2f) — kept '%.2f'",
                    dup["product_name"], store, float(dup["unit_price"]),
                    float(keep["unit_price"]),
                )
            except Exception as e:
                log.warning("Dedup: failed to remove dup %s: %s", dup["id"], e)

    # 4. Also update barcode_catalog keys
    bc_keys_updated = 0
    try:
        bc_result = db.table("barcode_catalog").select("id, product_name, product_key").limit(5000).execute()
        for bc in (bc_result.data or []):
            new_key = generate_product_key(bc["product_name"])
            if bc.get("product_key") != new_key:
                try:
                    db.table("barcode_catalog").update(
                        {"product_key": new_key}
                    ).eq("id", bc["id"]).execute()
                    bc_keys_updated += 1
                except Exception:
                    pass
    except Exception as e:
        log.warning("Dedup: barcode_catalog update failed: %s", e)

    summary = {
        "total_scanned": len(all_products),
        "keys_updated": keys_updated,
        "duplicates_merged": merged,
        "barcode_keys_updated": bc_keys_updated,
    }

    log.info("Dedup complete: %s", summary)
    return summary


def setup_dedup_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Run dedup every Sunday at 03:00 UTC."""
    scheduler.add_job(
        run_dedup_job,
        "cron",
        day_of_week="sun",
        hour=3,
        id="product_dedup_worker",
        replace_existing=True,
    )
    log.info("Product dedup worker scheduled: every Sunday at 03:00 UTC")
