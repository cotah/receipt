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
    """OCR using OpenAI gpt-4.1-mini Vision (fallback when Gemini unavailable)."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"
    response = await asyncio.wait_for(
        openai_client.chat.completions.create(
            model="gpt-4.1-mini",
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

    # Fallback: OpenAI Vision
    try:
        log.info("OCR: calling OpenAI Vision (gpt-4.1-mini)...")
        text = await _openai_ocr(OCR_PROMPT, image_bytes)
        log.info(f"OCR: OpenAI Vision succeeded ({len(text)} chars)")
        return text
    except Exception as e:
        log.error(f"OCR: OpenAI Vision also failed: {type(e).__name__}: {e}")
        raise RuntimeError(f"OCR failed — both Gemini and OpenAI Vision unavailable: {e}")


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


SHELF_PRICE_PROMPT = """
You are a deterministic shelf-label extraction engine for Irish supermarkets. Your sole function is to read every visible price tag/label in a photograph and output structured product data. Your output is parsed programmatically.

OUTPUT CONTRACT: For each visible price label, output EXACTLY one line: PRODUCT_NAME | PRICE | CATEGORY
One product per line. No blank lines. Zero text before or after. No explanations. No reasoning. No markdown. No headers. No numbering. Separator is: space, pipe, space ( | ). If ZERO price labels are visible → output the single word: NONE

THE 8 EXTRACTION LAWS:

LAW 1 — SCAN COMPLETENESS: Extract EVERY price tag/label visible in the image. Scan left to right, top to bottom. After initial scan, re-scan image edges and corners — labels there are frequently missed. Check shelf edge strips, stickers on packaging, hanging tags, digital screens, promotional cards. Count your lines — if you see more labels than lines, re-scan.

LAW 2 — PRODUCT NAME CONSTRUCTION: Build as BRAND + PRODUCT DESCRIPTION + SIZE/WEIGHT from what is VISIBLE on the label. Include brand if visible (Tesco, Aldi, Lidl, SuperValu, Dunnes, or manufacturer brand). Include full description as printed. Include size/weight/volume if visible (g, kg, ml, L, cl, pk, pack, x). Use Title Case. If partially obscured but readable, include what you can read. NEVER invent or guess text not visible on the label.

LAW 3 — PRICE EXTRACTION (CURRENT PRICE ONLY): Extract as decimal number WITHOUT currency symbol (2.39 not €2.39). Price hierarchy — use FIRST match: 1) Promotional/sale/offer price (highlighted yellow/red tag), 2) Clubcard/loyalty price (if active displayed price), 3) Regular price. IGNORE: crossed-out old prices, "price per kg/100g/litre", "price per wash/sheet/unit", multi-buy totals ("2 for €5") unless single-unit price also shown, deposit info. Special: "€2.50 each or 2 for €4" → use 2.50. Large "2" small "39" → 2.39. "99c" → 0.99. "€1" → 1.00.

LAW 4 — CATEGORY ASSIGNMENT: Assign EXACTLY ONE from: Fruit & Veg (fresh/packaged fruits, vegetables, salads, herbs, potatoes, fresh soup, hummus), Dairy (milk, cheese, yoghurt, cream, butter, eggs, dairy alternatives), Meat & Fish (fresh/chilled meat, poultry, fish, seafood, deli meats, sausages, rashers, mince), Bakery (bread, rolls, wraps, bagels, cakes, pastries, tortillas, pitta), Frozen (frozen meals/pizza/chips/veg/fish, ice cream, frozen desserts/meat/fruit), Drinks (water, juice, soft drinks, tea, coffee, energy drinks, cordial), Snacks & Confectionery (crisps, chocolate, sweets, biscuits, cereal bars, popcorn, crackers), Personal Care (shampoo, soap, toothpaste, deodorant, razors, skincare, sanitary products), Cleaning & Household (cleaning sprays, washing-up liquid, laundry detergent, bin bags, foil, kitchen roll, toilet paper), Baby & Toddler (nappies, baby food, baby wipes, formula), Pet Food (dog/cat food, pet treats), Pantry (pasta, rice, flour, sugar, oil, sauces, condiments, spices, tinned goods, cereal, porridge, baking), Alcohol (beer, wine, spirits, cider), Other (gift cards, magazines, anything not fitting above). Ambiguity: frozen pizza → Frozen; chocolate biscuits → Snacks & Confectionery; flavoured milk → Dairy; chilled soup → Fruit & Veg; ambient soup → Pantry; plant milk → Dairy.

LAW 5 — WHAT TO SKIP: Do NOT extract: aisle markers/section headers, promotional banners with no specific product, store signage/branding, nutritional info panels, QR codes/barcodes alone, "price per kg/100g" labels appearing alone, loyalty scheme ads, multi-buy offers where no single-unit price is visible, labels where price is completely illegible.

LAW 6 — POOR IMAGE QUALITY: If name partially readable but price IS clear → extract with readable name. If price partially readable → SKIP. If reflected/glared but legible → extract. If extreme angle but legible → extract. If two labels overlap but distinguishable → extract both. If fully obscured → SKIP. NEVER guess a price you cannot read.

LAW 7 — IRISH LABEL FORMATS: TESCO: white labels blue/red text, yellow/orange = Clubcard offers (use Clubcard price), red = clearance. ALDI: simple white labels, Super 6 coloured labels for fruit/veg. LIDL: white labels with promotional strips. SUPERVALU: white labels, yellow = Real Rewards, red/orange = special offers. DUNNES: white labels green accents, "Everyday Value" = own brand, "Simply Better" = premium.

LAW 8 — DUPLICATE DETECTION: If same product has regular label + promo sticker → extract ONCE with current/promo price. If two different sizes of same product with different prices → extract BOTH (they are distinct products).

SELF-VALIDATION: Every line matches TEXT | NUMBER | CATEGORY. Price is plain decimal (no €). Category is one of 14 values. No "per kg" prices. No crossed-out prices. No multi-buy-only labels. Label count matches visible count. No duplicates. If no labels: output NONE.
"""


async def extract_shelf_prices(image_bytes: bytes) -> list[dict]:
    """Extract product prices from a shelf/price tag photo."""
    import json as _json
    
    raw_text = None
    if _gemini_model is not None:
        try:
            log.info("Shelf OCR: calling Gemini Vision...")
            raw_text = await _gemini_ocr(SHELF_PRICE_PROMPT, image_bytes)
        except Exception as e:
            log.warning("Shelf OCR: Gemini failed: %s", e)

    if raw_text is None:
        raw_text = await _openai_ocr(SHELF_PRICE_PROMPT, image_bytes)

    if not raw_text:
        return []

    # Parse the pipe-delimited output
    products = []
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2:
            name = parts[0]
            try:
                price = float(parts[1].replace("€", "").replace(",", ".").strip())
            except (ValueError, TypeError):
                continue
            category = parts[2] if len(parts) >= 3 else "Other"
            if name and price > 0:
                products.append({
                    "product_name": name,
                    "unit_price": price,
                    "category": category,
                })

    log.info("Shelf OCR: extracted %d products", len(products))
    return products
