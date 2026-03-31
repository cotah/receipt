"""Product enrichment service.

Fills missing image_url for products in collective_prices using:
1. barcode_catalog (local) — products already scraped with images
2. Open Food Facts API (free, no key) — global product database

Also cross-references barcode_catalog with collective_prices
to link barcodes to products that don't have them yet.
"""

import logging
from datetime import datetime, timezone

import httpx

from app.database import get_service_client
from app.utils.text_utils import generate_product_key

log = logging.getLogger(__name__)

OFF_API = "https://world.openfoodfacts.org/api/v2/product"
OFF_SEARCH = "https://world.openfoodfacts.org/cgi/search.pl"
OFF_USER_AGENT = "SmartDocket/1.0 (report@smartdocket.ie)"


async def enrich_products_from_barcode_catalog() -> dict:
    """Cross-reference collective_prices with barcode_catalog.

    For products that have a matching product_key in barcode_catalog,
    copy the image_url to collective_prices.
    """
    db = get_service_client()
    updated = 0

    try:
        # Get products without images
        products = (
            db.table("collective_prices")
            .select("id, product_key, product_name")
            .is_("image_url", "null")
            .limit(500)
            .execute()
        )

        if not products.data:
            log.info("Enrichment: no products without images")
            return {"updated": 0, "source": "barcode_catalog"}

        # Get all barcodes with images
        barcodes = (
            db.table("barcode_catalog")
            .select("product_key, image_url, brand, category")
            .neq("image_url", "")
            .execute()
        )

        barcode_map = {}
        for b in (barcodes.data or []):
            barcode_map[b["product_key"]] = b

        for product in products.data:
            match = barcode_map.get(product["product_key"])
            if match and match.get("image_url"):
                update_data = {"image_url": match["image_url"]}
                # Also update category if it's "Other"
                if match.get("category") and match["category"] != "Other":
                    update_data["category"] = match["category"]

                db.table("collective_prices").update(
                    update_data
                ).eq("id", product["id"]).execute()
                updated += 1

    except Exception as e:
        log.error("Enrichment from barcode_catalog failed: %s", e)

    log.info("Enrichment: updated %d products from barcode_catalog", updated)
    return {"updated": updated, "source": "barcode_catalog"}


async def enrich_products_from_openfoodfacts(batch_size: int = 50) -> dict:
    """Fetch images from Open Food Facts for products that have barcodes but no image.

    Looks up barcodes in barcode_catalog, fetches product data from OFF,
    and updates both barcode_catalog and collective_prices with images.
    """
    db = get_service_client()
    updated_barcodes = 0
    updated_products = 0

    try:
        # Get barcodes without images
        barcodes = (
            db.table("barcode_catalog")
            .select("barcode, product_key, product_name, image_url")
            .or_("image_url.is.null,image_url.eq.")
            .limit(batch_size)
            .execute()
        )

        if not barcodes.data:
            log.info("OFF enrichment: all barcodes already have images")
            return {"updated_barcodes": 0, "updated_products": 0}

        async with httpx.AsyncClient(
            timeout=15,
            headers={"User-Agent": OFF_USER_AGENT},
        ) as client:
            for bc in barcodes.data:
                barcode = bc["barcode"]
                try:
                    resp = await client.get(
                        f"{OFF_API}/{barcode}.json",
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

                    # Update barcode_catalog
                    update_bc = {"image_url": image_url}
                    brand = product.get("brands")
                    if brand and not bc.get("brand"):
                        update_bc["brand"] = brand
                    category = product.get("categories", "")
                    if category:
                        # Take first category
                        first_cat = category.split(",")[0].strip()
                        if first_cat:
                            update_bc["category"] = first_cat

                    db.table("barcode_catalog").update(
                        update_bc
                    ).eq("barcode", barcode).execute()
                    updated_barcodes += 1

                    # Update matching products in collective_prices
                    db.table("collective_prices").update(
                        {"image_url": image_url}
                    ).eq(
                        "product_key", bc["product_key"]
                    ).is_(
                        "image_url", "null"
                    ).execute()
                    updated_products += 1

                except Exception as e:
                    log.warning("OFF lookup failed for %s: %s", barcode, e)

    except Exception as e:
        log.error("OFF enrichment failed: %s", e)

    log.info(
        "OFF enrichment: updated %d barcodes, %d products",
        updated_barcodes, updated_products,
    )
    return {
        "updated_barcodes": updated_barcodes,
        "updated_products": updated_products,
    }


async def run_full_enrichment() -> dict:
    """Run all enrichment steps in order."""
    log.info("Starting full product enrichment...")

    # Step 1: Local barcode_catalog → collective_prices
    r1 = await enrich_products_from_barcode_catalog()

    # Step 2: Open Food Facts → barcode_catalog + collective_prices
    r2 = await enrich_products_from_openfoodfacts(batch_size=100)

    result = {
        "barcode_catalog_matches": r1["updated"],
        "off_barcodes_enriched": r2["updated_barcodes"],
        "off_products_enriched": r2["updated_products"],
    }
    log.info("Enrichment complete: %s", result)
    return result
