import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
import fitz  # PyMuPDF
from bs4 import BeautifulSoup

from app.services.ocr_service import extract_text_from_pdf_page
from app.services.extraction_service import extract_leaflet_products
from app.utils.text_utils import generate_product_key
from app.utils.price_utils import get_ttl_days
from supabase import Client

log = logging.getLogger(__name__)

LEAFLET_SOURCES = {
    "Aldi": {
        "url": "https://www.aldi.ie/leaflet",
        "pdf_pattern": r"leaflet\.aldi\.ie",
        "parser": "aldi",
    },
}

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-IE,en;q=0.9",
}


async def fetch_and_process_leaflets(db: Client) -> None:
    """Download and process weekly leaflets from Irish supermarkets."""
    for store_name, source in LEAFLET_SOURCES.items():
        try:
            log.info(f"Processing {store_name} leaflet...")
            pdf_url = await find_latest_pdf(source)
            if pdf_url:
                await process_pdf_leaflet(db, store_name, pdf_url)
                log.info(f"{store_name} leaflet processed")
            else:
                log.warning(f"No PDF found for {store_name}")
        except Exception as e:
            log.error(f"Failed to process {store_name} leaflet: {e}")


async def _find_aldi_pdf(source: dict) -> str | None:
    """Find the Aldi leaflet PDF from aldi.ie/leaflet page.

    Priority:
    1. Direct CDN PDF link (cdn.aldi-digital.co.uk/*.pdf) — always works
    2. leaflet.aldi.ie slug — append /pdf (legacy, may 404)
    """
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30, headers=BROWSER_HEADERS,
        ) as client:
            response = await client.get(source["url"])
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Priority 1: Direct PDF link (CDN)
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.endswith(".pdf") and "aldi" in href.lower():
                log.info("Aldi: found direct PDF at %s", href)
                return href

        # Priority 2: Any .pdf link
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.endswith(".pdf"):
                log.info("Aldi: found PDF link at %s", href)
                return href

        # Priority 3: leaflet.aldi.ie slug → /pdf (may 404)
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "leaflet.aldi.ie" in href:
                slug_url = href.rstrip("/")
                pdf_url = f"{slug_url}/pdf"
                log.info("Aldi: trying leaflet slug PDF at %s", pdf_url)
                return pdf_url

    except Exception as e:
        log.error("Aldi: error finding PDF: %s", e)

    return None


async def find_latest_pdf(source: dict) -> str | None:
    """Find the latest PDF URL from a store's offers page."""
    parser = source.get("parser")

    if parser == "aldi":
        return await _find_aldi_pdf(source)

    if not source.get("pdf_pattern"):
        return None

    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30, headers=BROWSER_HEADERS,
        ) as client:
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

                db.table("collective_prices").upsert({
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
                }, on_conflict="product_key,store_name,source").execute()
                total_items += 1

        total_pages = len(doc)
        doc.close()

        # Update leaflet status
        if leaflet_id:
            db.table("leaflets").update({
                "status": "done",
                "page_count": total_pages,
                "items_extracted": total_items,
            }).eq("id", leaflet_id).execute()

    except Exception as e:
        log.error(f"Error processing PDF for {store_name}: {e}")
        if leaflet_id:
            db.table("leaflets").update({"status": "failed"}).eq("id", leaflet_id).execute()
        raise
