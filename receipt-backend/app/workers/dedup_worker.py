"""Product deduplication worker.

Runs weekly to find and merge duplicate products in collective_prices.
Uses the order-independent generate_product_key to identify duplicates.

OPTIMIZED: Uses batch deletes instead of individual operations.
Handles thousands of duplicates in under 60 seconds.
"""
import logging
from collections import defaultdict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import get_service_client
from app.utils.text_utils import generate_product_key

log = logging.getLogger(__name__)

BATCH_SIZE = 50  # IDs per batch operation


async def run_dedup_job() -> dict:
    """Scan collective_prices for duplicates and merge them."""
    log.info("Starting product deduplication scan...")

    db = get_service_client()

    # Fetch all products (paginate)
    all_products = []
    offset = 0
    page_size = 1000
    while True:
        result = (
            db.table("collective_prices")
            .select("id, product_name, product_key, store_name, unit_price")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not result.data:
            break
        all_products.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size

    log.info("Dedup: scanned %d products", len(all_products))

    # 1. Group by NEW key + store -> find duplicates
    by_key_store = defaultdict(list)
    for p in all_products:
        new_key = generate_product_key(p["product_name"])
        by_key_store[(new_key, p["store_name"])].append(p)

    # 2. Collect IDs to delete (keep cheapest per group)
    ids_to_delete = []
    for (key, store), entries in by_key_store.items():
        if len(entries) <= 1:
            continue
        entries.sort(key=lambda x: float(x["unit_price"]))
        # Keep first (cheapest), delete rest
        for dup in entries[1:]:
            ids_to_delete.append(dup["id"])

    log.info("Dedup: found %d duplicates to remove", len(ids_to_delete))

    # 3. BATCH delete in chunks
    merged = 0
    for i in range(0, len(ids_to_delete), BATCH_SIZE):
        batch = ids_to_delete[i:i + BATCH_SIZE]
        try:
            db.table("collective_prices").delete().in_("id", batch).execute()
            merged += len(batch)
            log.info("Dedup: deleted batch %d-%d (%d items)", i, i + len(batch), len(batch))
        except Exception as e:
            log.warning("Dedup: batch delete failed at offset %d: %s", i, e)
            # Fallback: individual deletes
            for did in batch:
                try:
                    db.table("collective_prices").delete().eq("id", did).execute()
                    merged += 1
                except Exception:
                    pass

    # 4. BATCH update product_keys to new sorted format
    keys_updated = 0
    deleted_set = set(ids_to_delete)
    by_new_key = defaultdict(list)
    for p in all_products:
        if p["id"] in deleted_set:
            continue
        new_key = generate_product_key(p["product_name"])
        if p["product_key"] != new_key:
            by_new_key[new_key].append(p["id"])

    for new_key, pids in by_new_key.items():
        for i in range(0, len(pids), BATCH_SIZE):
            batch = pids[i:i + BATCH_SIZE]
            try:
                db.table("collective_prices").update(
                    {"product_key": new_key}
                ).in_("id", batch).execute()
                keys_updated += len(batch)
            except Exception as e:
                log.warning("Dedup: key update failed for %s: %s", new_key, e)

    # 5. Update barcode_catalog keys
    bc_keys_updated = 0
    try:
        bc_all = []
        bc_offset = 0
        while True:
            bc_result = (
                db.table("barcode_catalog")
                .select("id, product_name, product_key")
                .range(bc_offset, bc_offset + page_size - 1)
                .execute()
            )
            if not bc_result.data:
                break
            bc_all.extend(bc_result.data)
            if len(bc_result.data) < page_size:
                break
            bc_offset += page_size

        bc_by_key = defaultdict(list)
        for bc in bc_all:
            new_key = generate_product_key(bc["product_name"])
            if bc.get("product_key") != new_key:
                bc_by_key[new_key].append(bc["id"])

        for new_key, bids in bc_by_key.items():
            for i in range(0, len(bids), BATCH_SIZE):
                batch = bids[i:i + BATCH_SIZE]
                try:
                    db.table("barcode_catalog").update(
                        {"product_key": new_key}
                    ).in_("id", batch).execute()
                    bc_keys_updated += len(batch)
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
