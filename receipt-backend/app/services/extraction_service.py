import json
from openai import AsyncOpenAI
from app.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

EXTRACTION_PROMPT = """
You are a receipt data extractor. Given raw text from an Irish supermarket receipt,
extract structured data and return ONLY valid JSON. No explanation, no markdown.

Normalise product names (e.g. "BANANAS LH KG" → "Banana").
Detect category from: Fruit & Veg, Dairy, Meat & Fish, Bakery, Frozen,
Drinks, Snacks & Confectionery, Household, Personal Care, Baby & Kids, Other.
Detect store: Lidl/Aldi/Tesco/SuperValu/Dunnes/Other.
All prices in EUR as decimal numbers.

Return this exact JSON structure:
{{
  "store_name": "Lidl",
  "store_branch": "Lidl Rathmines",
  "purchased_at": "2026-03-20T14:30:00",
  "subtotal": 51.03,
  "discount_total": 3.20,
  "total_amount": 47.83,
  "items": [
    {{
      "raw_name": "BANANAS LH KG",
      "normalized_name": "Banana",
      "category": "Fruit & Veg",
      "brand": null,
      "quantity": 1.2,
      "unit": "kg",
      "unit_price": 0.99,
      "total_price": 1.19,
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

IMPORTANT: Extract ONLY food and drink products.
Ignore clothing, garden, tools, household appliances, or any non-food items.
Use common sense — jacket potato is food, plant-based milk is food.

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

Categories (food only): Fruit & Veg, Dairy, Meat & Fish, Bakery, Frozen,
Drinks, Snacks & Confectionery, Other.

If no food products exist in the text, return an empty array: []

RAW TEXT:
{raw_text}
"""


async def extract_receipt_data(raw_text: str) -> dict:
    """Extract structured receipt data from raw OCR text using GPT."""
    response = await client.chat.completions.create(
        model="gpt-5.4-nano",
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
