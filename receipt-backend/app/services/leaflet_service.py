import logging
import re
from datetime import datetime, timedelta, timezone
import httpx
import fitz  # PyMuPDF
from app.services.ocr_service import extract_text_from_pdf_page
from app.services.extraction_service import extract_leaflet_products
from app.utils.text_utils import generate_product_key
from app.utils.price_utils import get_ttl_days
from supabase import Client

log = logging.getLogger(__name__)

LEAFLET_SOURCES = {
    "Lidl": {
        "url": "https://www.lidl.ie/c/weekly-offers/s10024218",
        "pdf_pattern": r"lidl\.ie.*\.pdf",
    },
    "Aldi": {
        "url": "https://www.aldi.ie/offers",
        "pdf_pattern": r"aldi\.ie.*\.pdf",
    },
    "SuperValu": {
        "url": "https://supervalu.ie/real-food/offers",
        "pdf_pattern": None,
    },
}


async def fetch_and_process_leaflets(db: Client) -> None:
    """Download and process weekly leaflets from Irish supermarkets."""
    for store_name, source in LEAFLET_SOURCES.items():
        try:
            log.info(f"Processing {store_name} leaflet...")
            pdf_url = await find_latest_pdf(source)
            if pdf_url:
                await process_pdf_leaflet(db, store_name, pdf_url)
                log.info(f"✓ {store_name} leaflet processed")
            else:
                log.warning(f"No PDF found for {store_name}")
        except Exception as e:
            log.error(f"Failed to process {store_name} leaflet: {e}")


async def find_latest_pdf(source: dict) -> str | None:
    """Find the latest PDF URL from a store's offers page."""
    if not source.get("pdf_pattern"):
        return None

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            response = await client.get(source["url"])
            response.raise_for_status()

        # Look for PDF links in the HTML
        pattern = source["pdf_pattern"]
        matches = re.findall(
            r'href=["\']?(https?://[^"\'>\s]*?' + pattern + r')["\']?',
            response.text,
            re.IGNORECASE,
        )
        if matches:
            return matches[0]

        # Try finding any PDF link
        pdf_links = re.findall(
            r'href=["\']?(https?://[^"\'>\s]*?\.pdf)["\']?',
            response.text,
            re.IGNORECASE,
        )
        return pdf_links[0] if pdf_links else None
    except Exception as e:
        log.error(f"Error finding PDF: {e}")
        return None


async def process_pdf_leaflet(db: Client, store_name: str, pdf_url: str) -> None:
    """Download PDF, convert pages to images, OCR, extract products."""
    # Create leaflet record
    now = datetime.now(timezone.utc)
    valid_from = now.date()
    valid_until = (now + timedelta(days=6)).date()

    leaflet = db.table("leaflets").insert({
        "store_name": store_name,
        "valid_from": valid_from.isoformat(),
        "valid_until": valid_until.isoformat(),
        "pdf_url": pdf_url,
        "status": "processing",
    }).execute()
    leaflet_id = leaflet.data[0]["id"] if leaflet.data else None

    try:
        # Download PDF
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            response = await client.get(pdf_url)
            response.raise_for_status()
            pdf_bytes = response.content

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_items = 0

        for page_num in range(len(doc)):
            page = doc[page_num]
            mat = fitz.Matrix(2, 2)  # 2x zoom for better OCR
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("jpeg")

            # OCR with Gemini
            raw_text = await extract_text_from_pdf_page(img_bytes)

            # Extract products with GPT
            products = await extract_leaflet_products(raw_text, store_name)

            # Save to collective prices
            for product in products:
                product_key = generate_product_key(
                    product.get("product_name", ""),
                    product.get("unit"),
                )
                category = product.get("category", "Other")
                ttl_days = get_ttl_days(category)

                db.table("collective_prices").insert({
                    "product_key": product_key,
                    "product_name": product.get("product_name", "Unknown"),
                    "category": category,
                    "store_name": store_name,
                    "unit_price": product.get("unit_price", 0),
                    "unit": product.get("unit"),
                    "is_on_offer": product.get("is_on_offer", True),
                    "source": "leaflet",
                    "observed_at": now.isoformat(),
                    "expires_at": (now + timedelta(days=max(ttl_days, 7))).isoformat(),
                }).execute()
                total_items += 1

        doc.close()

        # Update leaflet status
        if leaflet_id:
            db.table("leaflets").update({
                "status": "done",
                "page_count": len(doc) if not doc.is_closed else page_num + 1,
                "items_extracted": total_items,
            }).eq("id", leaflet_id).execute()

    except Exception as e:
        log.error(f"Error processing PDF for {store_name}: {e}")
        if leaflet_id:
            db.table("leaflets").update({"status": "failed"}).eq("id", leaflet_id).execute()
        raise
