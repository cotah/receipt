import json
from openai import AsyncOpenAI
from app.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

EXTRACTION_PROMPT = """
You are an expert receipt data extractor for Irish supermarkets.
Given raw text from a grocery receipt, extract structured data.
Return ONLY valid JSON. No explanation, no markdown fences.

CRITICAL RULES FOR IRISH RECEIPT FORMATS:

1. QUANTITY LINES: When you see a line like "2 x 1.79" or "3 x 0.99",
   it refers to the product on the PREVIOUS line. It means:
   - quantity = 2 (or 3)
   - unit_price = 1.79 (or 0.99)
   - total_price = the amount shown on the PREVIOUS product line
   Example:
     STRAIGHT CUT CHIPS    1.55 E    ← total_price is 1.55 (deal price for 2)
     2 x                   1.79      ← quantity=2, unit_price=1.79 (original each)
   This means: 2 chips, unit_price €1.79 each, but total is €1.55 (multi-buy deal)
   The "2 x 1.79" line is NOT a separate product.

2. ALDI format:
   - Product code + NAME + PRICE + E (E=VAT exempt)
   - "2 x PRICE" on next line = quantity/unit for PREVIOUS item
   - Total line at bottom
   - Date at bottom (DD/MM/YY format)

3. TESCO format:
   - NAME + PRICE on each line
   - "Qty X @ PRICE" or "X x PRICE" = quantity for previous item
   - "Clubcard Price" or "Promotional Saving" lines = discounts
   - "Meal Deal" lines = bundle discounts

4. LIDL format:
   - Similar to Aldi: code + NAME + PRICE
   - Quantity lines below
   - Deposit lines for bottles

5. SUPERVALU format:
   - NAME + PRICE
   - "X @ PRICE" = quantity lines
   - "Multibuy Save" = discount

6. PRICE RULES:
   - unit_price = price PER SINGLE UNIT (before multi-buy deals)
   - total_price = actual amount charged for this line item
   - If "2 x 1.79" and line shows 3.58: unit_price=1.79, quantity=2, total_price=3.58
   - If "2 x 1.79" and line shows 1.55: unit_price=1.79, quantity=2, total_price=1.55 (deal)
   - discount_amount = difference if deal applies

7. VALIDATION: Sum of all total_price values should equal or be close to the receipt total.
   If your extraction doesn't add up, re-check the quantities and prices.

8. NORMALIZE product names: "STRGHT CT CHIPS" → "Straight Cut Chips"
   Keep brand names when visible. Include weight/size if shown.

Categories: Fruit & Veg, Dairy, Meat & Fish, Bakery, Frozen,
Drinks, Snacks & Confectionery, Household, Personal Care, Baby & Kids, Other.

Return this exact JSON structure:
{{
  "store_name": "Aldi",
  "store_branch": "Aldi Rathmines",
  "purchased_at": "2026-03-26T19:31:00",
  "subtotal": 6.62,
  "discount_total": 0,
  "total_amount": 6.62,
  "items": [
    {{
      "raw_name": "STRAIGHT CUT CHIPS",
      "normalized_name": "Straight Cut Chips",
      "category": "Frozen",
      "brand": null,
      "quantity": 2,
      "unit": "pack",
      "unit_price": 1.79,
      "total_price": 1.55,
      "discount_amount": 2.03,
      "is_on_offer": true
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
    response = await client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[
            {"role": "user", "content": EXTRACTION_PROMPT.format(raw_text=raw_text)}
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_completion_tokens=4000,
    )
    return json.loads(response.choices[0].message.content)


async def extract_leaflet_products(raw_text: str, store_name: str) -> list[dict]:
    """Extract products from leaflet OCR text."""
    response = await client.chat.completions.create(
        model="gpt-4.1-nano",
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
