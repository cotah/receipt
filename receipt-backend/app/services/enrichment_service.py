"""Product enrichment service.

Fills missing image_url for products using 4 sources (in order):
1. barcode_catalog (local) — cross-reference with existing data
2. Open Food Facts (free, no key) — global product database
3. UPCitemdb (100/day free, no key) — US/international products
4. Google Custom Search Images (100/day free, needs API key) — fallback

Daily budget: ~300 free lookups (100 OFF + 100 UPC + 100 Google).
"""

import logging
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.database import get_service_client

log = logging.getLogger(__name__)

OFF_API = "https://world.openfoodfacts.org/api/v2/product"
UPC_API = "https://api.upcitemdb.com/prod/trial/lookup"
GOOGLE_CSE_API = "https://www.googleapis.com/customsearch/v1"
USER_AGENT = "SmartDocket/1.0 (report@smartdocket.ie)"


# --- Source 1: Local barcode_catalog -> collective_prices ---

async def enrich_from_barcode_catalog() -> int:
    """Copy image_url from barcode_catalog to matching products."""
    db = get_service_client()
    updated = 0
    try:
        products = (
            db.table("collective_prices")
            .select("id, product_key")
            .is_("image_url", "null")
            .limit(500)
            .execute()
        )
        if not products.data:
            return 0

        barcodes = (
            db.table("barcode_catalog")
            .select("product_key, image_url, category")
            .neq("image_url", "")
            .execute()
        )
        bc_map = {b["product_key"]: b for b in (barcodes.data or [])}

        for p in products.data:
            match = bc_map.get(p["product_key"])
            if match and match.get("image_url"):
                update = {"image_url": match["image_url"]}
                if match.get("category") and match["category"] != "Other":
                    update["category"] = match["category"]
                db.table("collective_prices").update(update).eq("id", p["id"]).execute()
                updated += 1
    except Exception as e:
        log.error("Enrichment (barcode_catalog): %s", e)

    log.info("Enrichment (barcode_catalog): %d products updated", updated)
    return updated


# --- Source 2: Open Food Facts ---

async def enrich_from_openfoodfacts(batch_size: int = 100) -> int:
    """Fetch images from Open Food Facts for barcodes without images."""
    db = get_service_client()
    updated = 0
    try:
        barcodes = (
            db.table("barcode_catalog")
            .select("barcode, product_key")
            .or_("image_url.is.null,image_url.eq.")
            .limit(batch_size)
            .execute()
        )
        if not barcodes.data:
            return 0

        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
            for bc in barcodes.data:
                try:
                    resp = await client.get(
                        f"{OFF_API}/{bc['barcode']}.json",
                        params={"fields": "product_name,brands,image_url,categories"},
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    if data.get("status") != 1:
                        continue
                    product = data.get("product", {})
                    image_url = product.get("image_url")
                    if not image_url:
                        continue

                    update_bc = {"image_url": image_url}
                    brand = product.get("brands")
                    if brand:
                        update_bc["brand"] = brand
                    db.table("barcode_catalog").update(update_bc).eq("barcode", bc["barcode"]).execute()

                    db.table("collective_prices").update(
                        {"image_url": image_url}
                    ).eq("product_key", bc["product_key"]).is_("image_url", "null").execute()
                    updated += 1
                except Exception as e:
                    log.warning("OFF lookup %s: %s", bc["barcode"], e)
    except Exception as e:
        log.error("Enrichment (OFF): %s", e)

    log.info("Enrichment (OFF): %d images found", updated)
    return updated


# --- Source 3: UPCitemdb ---

async def enrich_from_upcitemdb(batch_size: int = 100) -> int:
    """Fetch images from UPCitemdb (100/day free, no key needed)."""
    db = get_service_client()
    updated = 0
    try:
        barcodes = (
            db.table("barcode_catalog")
            .select("barcode, product_key")
            .or_("image_url.is.null,image_url.eq.")
            .limit(batch_size)
            .execute()
        )
        if not barcodes.data:
            return 0

        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
            for bc in barcodes.data:
                try:
                    resp = await client.get(
                        UPC_API,
                        params={"upc": bc["barcode"]},
                        headers={"Accept": "application/json"},
                    )
                    if resp.status_code == 429:
                        log.info("UPCitemdb: rate limit hit, stopping")
                        break
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    items = data.get("items", [])
                    if not items:
                        continue
                    item = items[0]
                    images = item.get("images", [])
                    if not images:
                        continue

                    image_url = images[0]
                    update_bc = {"image_url": image_url}
                    brand = item.get("brand")
                    if brand:
                        update_bc["brand"] = brand
                    category = item.get("category")
                    if category:
                        update_bc["category"] = category
                    db.table("barcode_catalog").update(update_bc).eq("barcode", bc["barcode"]).execute()

                    db.table("collective_prices").update(
                        {"image_url": image_url}
                    ).eq("product_key", bc["product_key"]).is_("image_url", "null").execute()
                    updated += 1
                except Exception as e:
                    log.warning("UPCitemdb lookup %s: %s", bc["barcode"], e)
    except Exception as e:
        log.error("Enrichment (UPCitemdb): %s", e)

    log.info("Enrichment (UPCitemdb): %d images found", updated)
    return updated


# --- Source 4: Google Custom Search Images ---

async def enrich_from_google_cse(batch_size: int = 100) -> int:
    """Search Google Images for products without photos (100/day free)."""
    api_key = settings.GOOGLE_CSE_API_KEY
    cse_id = settings.GOOGLE_CSE_ID
    if not api_key or not cse_id:
        log.info("Google CSE: not configured, skipping")
        return 0

    db = get_service_client()
    updated = 0
    try:
        products = (
            db.table("collective_prices")
            .select("id, product_key, product_name")
            .is_("image_url", "null")
            .limit(batch_size * 3)
            .execute()
        )
        if not products.data:
            return 0

        seen_keys = set()
        unique = []
        for p in products.data:
            if p["product_key"] not in seen_keys:
                seen_keys.add(p["product_key"])
                unique.append(p)
        unique = unique[:batch_size]

        async with httpx.AsyncClient(timeout=15) as client:
            for p in unique:
                try:
                    resp = await client.get(
                        GOOGLE_CSE_API,
                        params={
                            "key": api_key,
                            "cx": cse_id,
                            "q": f"{p['product_name']} grocery product",
                            "searchType": "image",
                            "num": 1,
                            "imgSize": "medium",
                            "safe": "active",
                        },
                    )
                    if resp.status_code == 429 or resp.status_code == 403:
                        log.info("Google CSE: quota/auth issue (%d), stopping", resp.status_code)
                        break
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    items = data.get("items", [])
                    if not items:
                        continue

                    image_url = items[0].get("link")
                    if not image_url:
                        continue

                    db.table("collective_prices").update(
                        {"image_url": image_url}
                    ).eq("product_key", p["product_key"]).is_("image_url", "null").execute()

                    db.table("barcode_catalog").update(
                        {"image_url": image_url}
                    ).eq("product_key", p["product_key"]).or_("image_url.is.null,image_url.eq.").execute()
                    updated += 1
                except Exception as e:
                    log.warning("Google CSE '%s': %s", p["product_name"][:30], e)
    except Exception as e:
        log.error("Enrichment (Google CSE): %s", e)

    log.info("Enrichment (Google CSE): %d images found", updated)
    return updated


# --- Main orchestrator ---

async def run_full_enrichment() -> dict:
    """Run all enrichment sources in order. ~300 free lookups/day."""
    log.info("Starting full product enrichment (4 sources)...")

    r1 = await enrich_from_barcode_catalog()
    r2 = await enrich_from_openfoodfacts(batch_size=100)
    r3 = await enrich_from_upcitemdb(batch_size=100)
    r4 = await enrich_from_google_cse(batch_size=100)

    result = {
        "barcode_catalog": r1,
        "open_food_facts": r2,
        "upcitemdb": r3,
        "google_cse": r4,
        "total_enriched": r1 + r2 + r3 + r4,
    }
    log.info("Enrichment complete: %s", result)
    return result
