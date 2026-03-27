import asyncio
import base64
import logging

from openai import AsyncOpenAI

from app.config import settings

log = logging.getLogger(__name__)

# --- Gemini setup (optional — broken on Python 3.14 due to protobuf) ---
_gemini_model = None
try:
    import google.generativeai as genai

    genai.configure(api_key=settings.GOOGLE_API_KEY)
    _gemini_model = genai.GenerativeModel("gemini-2.5-flash")
    log.info("OCR: Gemini Vision available")
except Exception as e:
    log.warning(f"OCR: Gemini Vision unavailable ({type(e).__name__}: {e}), will use OpenAI Vision only")

# --- OpenAI setup (primary fallback / sole provider) ---
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

OCR_TIMEOUT = 45  # seconds (leaflet pages are dense)

OCR_PROMPT = """
You are reading an Irish supermarket grocery receipt. Extract ALL text with EXACT precision.

STEP 1 — VALIDATE: Is this a grocery receipt from Tesco, Lidl, Aldi, Dunnes, or SuperValu Ireland?
If NOT, respond with exactly: NOT_A_RECEIPT

STEP 2 — EXTRACT with these critical rules:
- Extract EVERY line exactly as printed, including product codes/numbers
- PRESERVE quantity lines like "2 x 1.79" or "3 @ 0.99" — keep them on their own line
- PRESERVE the exact price on each line (do NOT recalculate)
- Include ALL: store name, branch, date, time, every item line, every quantity line,
  every discount line, subtotal, VAT, total, payment method
- Keep the original line-by-line layout
- Do NOT skip any line, even if it looks like a duplicate
- Do NOT merge quantity lines with product lines
- Extract date in whatever format appears (DD/MM/YY, DD.MM.YYYY, etc)

Output plain text only, no markdown, no interpretation.
"""

LEAFLET_OCR_PROMPT = """
You are extracting products from an Irish supermarket weekly leaflet/flyer page.

CRITICAL: Extract EVERY single product visible on this page. Do NOT skip any.
Many leaflet pages have 5-15 products. If you see prices, there are products.

For each product, output one line:
PRODUCT_NAME | PRICE | CATEGORY

Where:
- PRODUCT_NAME is the full product name as shown (include brand, size, weight)
- PRICE is the numeric price in EUR (e.g. 1.49). Look carefully at price labels.
- CATEGORY is one of: Fruit & Veg, Dairy, Meat & Fish, Bakery, Frozen, Drinks, Snacks & Confectionery, Personal Care, Cleaning & Household, Baby & Toddler, Pet Food, Other

INCLUDE: All food, drinks, alcohol, personal care, cleaning products, pet food.
EXCLUDE: Clothing, power tools, electronics, furniture, garden equipment, toys.

Be thorough — extract ALL products you can see, even partially visible ones.
If you can see a price tag next to a product, include it.
If no grocery products exist, output nothing.
"""

LEAFLET_DIRECT_EXTRACTION_PROMPT = """
You are extracting products from an Irish supermarket weekly leaflet page image.

CRITICAL RULES:
1. Extract EVERY grocery product visible. Do NOT skip any.
2. Look carefully at EVERY price label on the page.
3. Typical leaflet pages have 5-15 products. Count them.
4. Include ALL: food, drinks, alcohol, wine, beer, personal care, cleaning, pet food.
5. EXCLUDE: clothing, tools, electronics, furniture, garden equipment, toys.

Return ONLY a valid JSON array. No markdown, no explanation.

[
  {{"product_name": "Full Product Name With Brand and Size", "unit_price": 1.49, "category": "Dairy", "is_on_offer": true}},
  ...
]

Categories: Fruit & Veg, Dairy, Meat & Fish, Bakery, Frozen, Drinks,
Snacks & Confectionery, Personal Care, Cleaning & Household, Baby & Toddler, Pet Food, Other.

Be thorough. Every price tag = one product entry.
"""


def _gemini_sync(prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """Run Gemini generate_content synchronously (called from a thread)."""
    image_part = {"mime_type": mime_type, "data": image_bytes}
    response = _gemini_model.generate_content([prompt, image_part])
    return response.text


async def _gemini_ocr(prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """Call Gemini in a thread with a timeout."""
    if _gemini_model is None:
        raise RuntimeError("Gemini not available")
    return await asyncio.wait_for(
        asyncio.to_thread(_gemini_sync, prompt, image_bytes, mime_type),
        timeout=OCR_TIMEOUT,
    )


async def _openai_ocr(prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """OCR using OpenAI gpt-5.4 Vision."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"
    response = await asyncio.wait_for(
        openai_client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            max_completion_tokens=4000,
            temperature=0,
        ),
        timeout=OCR_TIMEOUT,
    )
    return response.choices[0].message.content


async def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract raw text from a receipt image. Tries Gemini first, falls back to OpenAI."""
    # Try Gemini if available
    if _gemini_model is not None:
        try:
            log.info("OCR: calling Gemini Vision...")
            text = await _gemini_ocr(OCR_PROMPT, image_bytes)
            log.info(f"OCR: Gemini succeeded ({len(text)} chars)")
            return text
        except asyncio.TimeoutError:
            log.warning(f"OCR: Gemini timed out after {OCR_TIMEOUT}s, falling back to OpenAI Vision")
        except Exception as e:
            log.warning(f"OCR: Gemini failed ({type(e).__name__}: {e}), falling back to OpenAI Vision")

    # Fallback / primary: OpenAI Vision
    log.info("OCR: calling OpenAI Vision (gpt-5.4)...")
    text = await _openai_ocr(OCR_PROMPT, image_bytes)
    log.info(f"OCR: OpenAI Vision succeeded ({len(text)} chars)")
    return text


async def extract_text_from_pdf_page(page_image_bytes: bytes) -> str:
    """Extract products from a leaflet page image. Tries Gemini first, falls back to OpenAI."""
    if _gemini_model is not None:
        try:
            text = await _gemini_ocr(LEAFLET_OCR_PROMPT, page_image_bytes)
            return text
        except asyncio.TimeoutError:
            log.warning(f"Leaflet OCR: Gemini timed out after {OCR_TIMEOUT}s, falling back to OpenAI")
        except Exception as e:
            log.warning(f"Leaflet OCR: Gemini failed ({type(e).__name__}: {e}), falling back to OpenAI")

    return await _openai_ocr(LEAFLET_OCR_PROMPT, page_image_bytes)


async def direct_extract_products_from_image(
    page_image_bytes: bytes,
    store_name: str = "Aldi",
) -> list[dict]:
    """Extract products DIRECTLY from a leaflet image in a single step.

    Sends the image to Gemini/OpenAI with a JSON extraction prompt,
    bypassing the intermediate OCR-to-text step. More accurate because
    the model can see the image layout and price labels directly.
    """
    import json as _json

    prompt = LEAFLET_DIRECT_EXTRACTION_PROMPT

    raw_text = None
    if _gemini_model is not None:
        try:
            raw_text = await _gemini_ocr(prompt, page_image_bytes)
        except Exception as e:
            log.warning("Direct extraction: Gemini failed: %s", e)

    if raw_text is None:
        raw_text = await _openai_ocr(prompt, page_image_bytes)

    if not raw_text:
        return []

    # Parse JSON from response
    try:
        # Strip markdown fences if present
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()
            if clean.startswith("json"):
                clean = clean[4:].strip()

        data = _json.loads(clean)
        if isinstance(data, dict):
            data = data.get("products", data.get("items", []))
        if not isinstance(data, list):
            return []

        # Validate and clean
        products = []
        for item in data:
            name = item.get("product_name", "")
            price = item.get("unit_price")
            if name and price is not None:
                try:
                    float(price)
                    products.append(item)
                except (ValueError, TypeError):
                    pass

        log.info(
            "Direct extraction [%s]: %d products from image",
            store_name, len(products),
        )
        return products

    except _json.JSONDecodeError as e:
        log.warning("Direct extraction: JSON parse failed: %s", e)
        return []
