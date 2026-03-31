import json
from openai import AsyncOpenAI
from app.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

EXTRACTION_PROMPT = """
You are an expert receipt data extractor for Irish supermarkets.
Given raw text from a grocery receipt, extract structured data.
Return ONLY valid JSON. No explanation, no markdown fences.

CRITICAL RULES FOR IRISH RECEIPT FORMATS:

1. MULTI-LINE PRODUCT NAMES: Product names often wrap to 2 or 3 lines.
   These MUST be combined into ONE product. Example:
     1 Tesco Slievenamon Irish Still  €1.59
       Spring Water 5l
   This is ONE product: "Tesco Slievenamon Irish Still Spring Water 5l" at €1.59.
   The second line has NO PRICE — that's how you know it's a continuation.
   NEVER split a wrapped name into two separate products.

2. QUANTITY LINES: When you see "2 x 1.79" or "3 x 0.99",
   it refers to the product on the PREVIOUS line. It means:
   - quantity = 2 (or 3)
   - unit_price = 1.79 (or 0.99)
   - total_price = the amount shown on the PREVIOUS product line
   The quantity line is NOT a separate product.

3. DISCOUNT LINES: Lines starting with "Cc", "Clubcard", "Saving",
   "Promotional", "Meal Deal", "Multibuy" are discounts.
   They are NOT products. Example:
     1 Cheez-it Snap'd Double Cheese 120g  €3.50
       Cc €1.75                            -€1.75
   The "Cc €1.75" line is a Clubcard discount: the product cost €3.50,
   discount is €1.75, so total_price = €1.75 (3.50 - 1.75).
   Another example:
     1 Dr. Oetker Ristorante Pollo Pizza 355g  €4.25
       Cc Any 2 For €6                         -€1.25
   Discount is €1.25, total_price = €3.00 (4.25 - 1.25).

4. DEPOSIT LINES: "Deposit charged €0.15" are NOT products. Skip them.

5. TESCO format:
   - "1" at line start = quantity 1
   - Product name wraps to next line (join them!)
   - "Cc" lines = Clubcard discount for previous product
   - Subtotal/Savings/Promotions at the bottom

6. ALDI format:
   - Product code + NAME + PRICE + E (E=VAT exempt)
   - "2 x PRICE" on next line = quantity for PREVIOUS item

7. LIDL format:
   - Similar to Aldi: code + NAME + PRICE
   - Quantity lines below

8. SUPERVALU format:
   - NAME + PRICE
   - "X @ PRICE" = quantity lines
   - "Multibuy Save" = discount

9. PRICE RULES:
   - unit_price = price PER SINGLE UNIT (the number shown on the receipt for that line)
   - total_price = actual amount charged (unit_price minus any discount)
   - If there's a "Cc" discount line with -€X.XX, then:
     total_price = unit_price - discount_amount
   - discount_amount = the absolute value of the negative number

10. VALIDATION: 
    - Count actual products carefully. A 12-item receipt must have 12 items.
    - Sum of all total_price values should be close to the receipt subtotal.
    - If your count seems low, re-read the text — you probably missed wrapped names.

11. NORMALIZE product names: "STRGHT CT CHIPS" → "Straight Cut Chips"
    Keep brand names. Include weight/size if shown.

Categories: Fruit & Veg, Dairy, Meat & Fish, Bakery, Frozen,
Drinks, Snacks & Confectionery, Household, Personal Care, Baby & Kids,
Pantry, Alcohol, Pet Food, Other.

Return this exact JSON structure:
{{
  "store_name": "Tesco",
  "store_branch": "Tesco Rathmines Metro",
  "purchased_at": "2026-03-26T19:07:00",
  "subtotal": 39.67,
  "discount_total": 8.55,
  "total_amount": 28.77,
  "items": [
    {{
      "raw_name": "Tesco Slievenamon Irish Still Spring Water 5l",
      "normalized_name": "Tesco Slievenamon Irish Still Spring Water 5L",
      "category": "Drinks",
      "brand": "Tesco",
      "quantity": 1,
      "unit": null,
      "unit_price": 1.59,
      "total_price": 1.59,
      "discount_amount": 0,
      "is_on_offer": false
    }}
  ]
}}

RAW RECEIPT TEXT:
{raw_text}
"""

LEAFLET_EXTRACTION_PROMPT = """
You are a leaflet product extractor for Irish supermarkets.
Given raw text extracted from a {store_name} weekly leaflet page, return a JSON array of products.

IMPORTANT: Extract ONLY supermarket grocery products. This includes:
- Food & drink (all categories)
- Personal hygiene & health (shampoo, toothpaste, soap, deodorant, vitamins)
- Household cleaning & laundry (detergent, washing powder, surface cleaner, bleach)
- Baby & pet food products
- Kitchen & cooking essentials (cooking oil, foil, cling film)

EXCLUDE (do NOT extract):
- Clothing, shoes, accessories
- Power tools, garden equipment, DIY items
- Electronics, appliances, gadgets
- Furniture, home decor, storage items
- Plants, flowers, garden plants
- Toys, books, stationery
- Seasonal decorations
- Automotive products

Use common sense — if it belongs in a supermarket grocery aisle, include it.

Return ONLY valid JSON array:
[
  {{
    "product_name": "Avocado",
    "unit_price": 0.49,
    "original_price": 0.99,
    "unit": "unit",
    "category": "Fruit & Veg",
    "is_on_offer": true
  }}
]

Categories: Fruit & Veg, Dairy, Meat & Fish, Bakery, Frozen,
Drinks, Snacks & Confectionery, Personal Care, Cleaning & Household,
Baby & Toddler, Pet Food, Other.

If no food products exist in the text, return an empty array: []

RAW TEXT:
{raw_text}
"""


async def extract_receipt_data(raw_text: str) -> dict:
    """Extract structured receipt data from raw OCR text using GPT."""
    import re
    import logging
    log = logging.getLogger(__name__)

    # Count expected items by looking for price patterns (€X.XX) in the text
    price_lines = len(re.findall(r'€\d+\.\d{2}\s*$', raw_text, re.MULTILINE))

    response = await client.chat.completions.create(
        model="gpt-5.4-nano",
        messages=[
            {"role": "user", "content": EXTRACTION_PROMPT.format(raw_text=raw_text)}
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_completion_tokens=4000,
    )

    data = json.loads(response.choices[0].message.content)
    items = data.get("items", [])

    # Validation: if extracted items seem way too few, retry with higher tokens
    if len(items) < 3 and price_lines > 5:
        log.warning(
            "Extraction got %d items but text has ~%d price lines — retrying",
            len(items), price_lines,
        )
        response = await client.chat.completions.create(
            model="gpt-5.4-nano",
            messages=[
                {"role": "user", "content": EXTRACTION_PROMPT.format(raw_text=raw_text)},
                {"role": "assistant", "content": response.choices[0].message.content},
                {"role": "user", "content": (
                    f"You only extracted {len(items)} items but this receipt has "
                    f"approximately {price_lines} products. Please re-extract ALL "
                    f"products from the receipt. Return the complete JSON."
                )},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_completion_tokens=6000,
        )
        retry_data = json.loads(response.choices[0].message.content)
        if len(retry_data.get("items", [])) > len(items):
            log.info("Retry got %d items (was %d)", len(retry_data["items"]), len(items))
            data = retry_data

    return data


async def extract_leaflet_products(raw_text: str, store_name: str) -> list[dict]:
    """Extract products from leaflet OCR text."""
    response = await client.chat.completions.create(
        model="gpt-5.4-nano",
        messages=[
            {
                "role": "user",
                "content": LEAFLET_EXTRACTION_PROMPT.format(
                    raw_text=raw_text, store_name=store_name
                ),
            }
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_completion_tokens=4000,
    )
    data = json.loads(response.choices[0].message.content)
    # Handle both {"items": [...]} and [...] formats
    if isinstance(data, list):
        return data
    return data.get("items", data.get("products", []))
