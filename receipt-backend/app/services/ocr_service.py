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
    _gemini_model = genai.GenerativeModel("gemini-2.0-flash")
    log.info("OCR: Gemini Vision available")
except Exception as e:
    log.warning(f"OCR: Gemini Vision unavailable ({type(e).__name__}: {e}), will use OpenAI Vision only")

# --- OpenAI setup (primary fallback / sole provider) ---
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

OCR_TIMEOUT = 30  # seconds

OCR_PROMPT = """
Extract ALL text from this supermarket receipt image exactly as it appears.
Preserve the layout — one item per line.
Include: store name, date, time, all items with prices, subtotal, discounts, total.
Do not interpret or modify — raw extraction only.
Output plain text, no markdown.
"""

LEAFLET_OCR_PROMPT = """
Extract all products and prices from this supermarket leaflet page.
For each item found, output one line in this format:
NAME | PRICE | UNIT | ON_OFFER(yes/no)

Where:
- NAME is the product name
- PRICE is the numeric price in EUR (e.g. 1.49)
- UNIT is kg, L, unit, pack, etc.
- ON_OFFER is "yes" if it's a special offer, "no" otherwise

Output only the extracted lines, no headers or explanations.
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
    """OCR using OpenAI gpt-4o Vision."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"
    response = await asyncio.wait_for(
        openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            max_tokens=4000,
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
    log.info("OCR: calling OpenAI Vision (gpt-4o)...")
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
