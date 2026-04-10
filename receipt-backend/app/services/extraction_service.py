import json
from openai import AsyncOpenAI
from app.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

EXTRACTION_PROMPT = """
You are a deterministic receipt data extraction engine. Your sole function is to convert raw OCR text from Irish grocery receipts into structured JSON. You operate inside a production pipeline — your output is parsed programmatically. Any deviation from the schema will cause errors.

OUTPUT CONTRACT: Return ONLY a single valid JSON object.
First character of output: {{
Last character of output: }}
Zero text before or after the JSON. No markdown fences. No backticks. No comments. No explanation.

OUTPUT SCHEMA (EVERY FIELD IS MANDATORY):
{{
  "store_name": string,
  "store_branch": string | null,
  "purchased_at": string (ISO 8601) | null,
  "subtotal": number,
  "discount_total": number,
  "total_amount": number,
  "items": [
    {{
      "raw_name": string,
      "normalized_name": string,
      "category": string,
      "brand": string | null,
      "quantity": number,
      "unit": string | null,
      "unit_price": number,
      "total_price": number,
      "discount_amount": number,
      "is_on_offer": boolean
    }}
  ]
}}

Field definitions:
- store_name: retailer brand ("Tesco", "Aldi", "Lidl", "SuperValu", "Dunnes Stores")
- store_branch: full branch name if identifiable from receipt header, else null
- purchased_at: transaction timestamp in ISO 8601; use date + time if both exist; null if neither
- subtotal: sum before discounts (the pre-discount total printed on the receipt)
- discount_total: absolute sum of all discounts applied (always >= 0)
- total_amount: final amount charged (subtotal - discount_total)
- items[].raw_name: exact text from receipt lines joined, trimmed, with price removed
- items[].normalized_name: human-readable expanded name (see NORMALIZATION rules)
- items[].category: exactly one of the 14 allowed categories (see below)
- items[].brand: brand name if identifiable, else null
- items[].quantity: number of units purchased (default 1)
- items[].unit: measurement unit if sold by weight/volume ("kg", "L", "g", "ml"), else null
- items[].unit_price: price per single unit as printed on receipt
- items[].total_price: actual amount charged for this item AFTER discount
- items[].discount_amount: absolute discount value applied to this item (>= 0, default 0)
- items[].is_on_offer: true if any discount/promotion applies, else false

THE 10 PARSING LAWS (INVIOLABLE):

LAW 1 — LINE CLASSIFICATION
Every line in a receipt is exactly ONE of these types:
- TYPE A — PRODUCT LINE: contains a product name AND a price (€X.XX or X.XX at end)
- TYPE B — CONTINUATION LINE: contains text but NO price → belongs to the product on the PREVIOUS Type A line
- TYPE C — QUANTITY/WEIGHT LINE: a line that contains ONLY numbers, multipliers, and optionally units. Matches patterns like: digit(s) x/×/@ digit(s).digit(s), or standalone weight/quantity info. These lines ALWAYS modify the PREVIOUS product and are NEVER products themselves. CRITICAL: a line like "3x 0.85" or "2 x 0.850" or "0.456 kg" or "3 @ 1.29" is ALWAYS TYPE C — it is quantity/weight info, NOT a product.
- TYPE D — DISCOUNT LINE: starts with or contains: Cc, Clubcard, Saving, Promotional, Meal Deal, Multibuy, Price Match, Deal, BOGOF, or has a negative price (-€X.XX) → modifies the PREVIOUS product
- TYPE E — DEPOSIT LINE: contains "Deposit" or "deposit" → SKIP ENTIRELY
- TYPE F — METADATA LINE: store header, address, date, time, subtotal, total, payment method, VAT summary, barcode, "Thank you", receipt number, cashier info → NOT a product, extract metadata only

Classification procedure for each line:
1. Does it match Type E? → skip
2. Does it match Type F? → extract metadata, skip as product
3. Does it match Type D? → apply discount to previous product
4. Does it match Type C? → apply quantity/weight to previous product
   CRITICAL CHECK: if the line contains ONLY digits, spaces, "x", "×", "@", ".", "kg", "g", "ml", "L" and NO alphabetic product name words → it is ALWAYS Type C, never Type A
5. Does it have a price (€X.XX pattern at or near end of line)? → Type A (new product)
6. No price found? → Type B (continuation of previous product name)

LAW 2 — MULTI-LINE NAME MERGING
When a Type B line follows a Type A line, concatenate them with a single space.
Multiple consecutive Type B lines all merge into the same product.
CRITICAL: the price may appear on the FIRST line or the LAST line of a multi-line block. Scan ALL lines in the block to find the price. The price is ALWAYS the rightmost €-prefixed or decimal number at the end of any line in the block.
NEVER create a product with quantity 0 or price 0.00 from a continuation line.

LAW 3 — QUANTITY/WEIGHT EXTRACTION
When a Type C line is found:
- Extract multiplier and per-unit price (or weight)
- Apply to the IMMEDIATELY PRECEDING product
- Set: quantity = multiplier, unit_price = per-unit price
- The total_price on the product line = quantity × unit_price (before discounts)
Patterns: "2 x 1.79" "3 x €0.99" "2 × 1.79" "4 @ 0.75" "4 @ €0.75" "3x 0.85" "0.456 kg" "2 x 0.850"
CRITICAL: Lines that contain ONLY numbers and x/×/@ symbols (no product name words) are ALWAYS quantity/weight info. They must NEVER be created as separate products. Examples:
  "3x 0.85" → quantity=3, unit_price=0.85 for the previous product
  "2 x 0.850" → quantity=2, unit_price=0.85 for the previous product  
  "0.456 kg" → weight info for the previous product (set unit="kg")
  "1 x 2.49" → quantity=1, unit_price=2.49 for the previous product

LAW 4 — DISCOUNT APPLICATION
When a Type D line is found:
- Extract the discount value (always treat as positive number)
- Apply to the IMMEDIATELY PRECEDING product
- Set: discount_amount = abs(discount_value), is_on_offer = true
- Recalculate: total_price = (unit_price × quantity) - discount_amount
Multiple discount lines may apply to the same product. Sum all discounts.
Patterns: "Cc €1.75 -€1.75" "Cc Any 2 For €6 -€1.25" "Clubcard Price -€0.50" "Promotional Saving -€1.00" "Meal Deal Saving -€2.00" "Multibuy Save -€0.30" "BOGOF -€3.50" "Price Match -€0.15"

LAW 5 — PRICE EXTRACTION
Prices appear as: €1.59 | 1.59 | EUR 1.59
- The RIGHTMOST number matching €?digit(s).digit(s) on a product line is the price
- Ignore leading digits that are quantity indicators (e.g., "1" at start of Tesco lines)
- Ignore product codes (e.g., "12345" at start of Aldi/Lidl lines)
- A trailing "E" or "A" after the price = VAT indicator, not part of the price
- Negative prices are ALWAYS discounts, never product prices.

LAW 6 — STORE-SPECIFIC PARSING
TESCO IRELAND: Line prefix "1" = quantity 1 (not a product code). Product names frequently span 2-3 lines. "Cc" prefix = Clubcard discount line. "Clubcard Price" = discount line. Footer contains SUBTOTAL, TOTAL, Clubcard savings summary. Branch name usually in header.
ALDI IRELAND: Format: [PRODUCT_CODE] PRODUCT_NAME PRICE [E|A]. Product codes are 5-8 digit numbers at line start — NOT quantity. "E" = VAT exempt, "A" = VAT applicable. Quantity appears on NEXT line: "2 x 1.79". No loyalty discount system.
LIDL IRELAND: Similar to Aldi format. Product code at start of line. "A" or "B" VAT indicator suffix. Quantity on next line.
SUPERVALU: Format: PRODUCT_NAME PRICE. Quantity: "X @ PRICE" on next line. "Multibuy Save" = discount line. May show "Was €X.XX Now €Y.YY" — use the "Now" price as unit_price.
DUNNES STORES: Format: PRODUCT_NAME PRICE. May prefix quantity on same line: "2 PRODUCT_NAME PRICE". Discounts shown as separate lines with negative values.

LAW 7 — NAME NORMALIZATION
Transform raw_name → normalized_name:
- Expand abbreviations: ORG→Organic, STRGHT→Straight, CT→Cut, SM→Small, LG→Large, MED→Medium, WHT→White, BRN→Brown, CHKN→Chicken, VEG→Vegetable, S/BERRY→Strawberry, B/BERRY→Blueberry, R/BERRY→Raspberry, CHOC→Chocolate, BTR→Butter, SK→Skimmed, S/SK→Semi-Skimmed, GRN→Green, YEL→Yellow, FR→Free Range, MLK→Milk, BRD→Bread, PCK→Pack, PK→Pack, FLWR→Flour, SGR→Sugar, O/NIGHT→Overnight, S/CREAM→Sour Cream, C/CHEESE→Cream Cheese, MAYO→Mayonnaise, UNSAL→Unsalted, SAL→Salted, XVIRGIN→Extra Virgin
- Convert to Title Case (except units: kg, g, ml, L)
- Preserve brand names exactly
- Preserve weight/volume/size (e.g., 5L, 355g, 500ml, 1kg, 6pk, 6 Pack)
- Remove leading quantity digits if redundant with the quantity field
- Trim extra whitespace

LAW 8 — CATEGORY ASSIGNMENT
Assign EXACTLY ONE category from this closed list:
- Fruit & Veg — fresh/frozen/tinned fruits, vegetables, salads, herbs, potatoes, mushrooms
- Dairy — milk, cheese, yoghurt, cream, butter, eggs, dairy alternatives (oat milk, soy milk)
- Meat & Fish — fresh/frozen/processed meat, poultry, fish, seafood, deli meats, sausages, rashers, mince
- Bakery — bread, rolls, wraps, bagels, croissants, muffins, scones, cakes, pastries, tortillas
- Frozen — frozen meals, frozen pizza, frozen chips, frozen veg, ice cream, frozen desserts
- Drinks — water, juice, soft drinks, tea, coffee, energy drinks, cordial, squash
- Snacks & Confectionery — crisps, chocolate, sweets, biscuits, cereal bars, popcorn, nuts (snack), crackers
- Household — cleaning products, bin bags, foil, cling film, kitchen roll, toilet paper, batteries, light bulbs, laundry
- Personal Care — shampoo, soap, toothpaste, deodorant, razors, skincare, sanitary products, tissues (facial)
- Baby & Kids — nappies, baby food, baby wipes, formula, baby toiletries
- Pantry — pasta, rice, flour, sugar, oil, vinegar, sauces, condiments, spices, tinned goods (non-fruit/veg), cereal, porridge, soup (ambient), stock cubes, baking ingredients
- Alcohol — beer, wine, spirits, cider, ready-to-drink cocktails
- Pet Food — dog food, cat food, pet treats, pet accessories
- Other — anything that doesn't clearly fit above; gift cards, magazines, stamps, phone credit
Decision procedure: Identify the PRIMARY product (ignore brand, modifiers). Match to the most specific category. When ambiguous: frozen pizza → Frozen; chocolate biscuits → Snacks & Confectionery; flavoured milk → Dairy; vegetable soup (ambient) → Pantry.

LAW 9 — ARITHMETIC INTEGRITY
For every item: total_price = (unit_price × quantity) - discount_amount
Global checks:
- SUM(items[].unit_price × items[].quantity) ≈ subtotal (tolerance: ±€0.05)
- SUM(items[].discount_amount) ≈ discount_total (tolerance: ±€0.05)
- subtotal - discount_total ≈ total_amount (tolerance: ±€0.05)
If these checks fail, re-examine the receipt text and correct your parsing before outputting.

LAW 10 — ITEM COUNT INTEGRITY
Before outputting, count your items array length.
Common errors that inflate count: continuation line as separate product, quantity line as product, discount line as product, deposit line as product.
Common errors that deflate count: two products on adjacent lines — second one skipped, short-named product missed.
Verification: if the receipt footer shows "X items", your items array length should match. If it shows a subtotal, your sum should match.

EDGE CASES (MANDATORY HANDLING):
- REDUCED/CLEARANCE ITEMS: "Was €X Now €Y" → use Now price as unit_price, discount_amount = original - reduced, is_on_offer = true
- WEIGHTED ITEMS: "0.547 kg @ €5.99/kg = €3.28" → quantity=0.547, unit="kg", unit_price=5.99, total_price=3.28
- REFUNDED ITEMS: Negative total on a product line → include with negative total_price
- MEAL DEAL BUNDLES: Apply full discount to last product before discount line. Set is_on_offer=true on all bundle products.
- COUPONS: "Coupon -€1.00" → discount on previous product. Basket-level coupons → add to discount_total, do NOT create product.
- BAG CHARGES: "Carrier Bag €0.22" → include as product with category "Other"
- EMPTY/UNREADABLE LINES: garbage OCR text with no product or price → SKIP
- DUPLICATE PRICES: "Product €2.00 €2.00" → rightmost is the charged price, ignore left duplicate.

SELF-VALIDATION CHECKLIST (RUN BEFORE OUTPUT):
- Output starts with {{ and ends with }}
- JSON is syntactically valid
- Every item has ALL 10 fields populated
- No item has unit_price = 0 (unless genuinely free)
- No item has quantity = 0
- total_price = (unit_price × quantity) - discount_amount for every item
- SUM(total_price) ≈ total_amount (±€0.05)
- SUM(discount_amount) ≈ discount_total (±€0.05)
- No discount/quantity/continuation/deposit line exists as a separate product
- category is one of the 14 allowed values (exact spelling)
- is_on_offer is true IFF discount_amount > 0
- purchased_at is ISO 8601 or null
- All number fields are actual numbers (not strings)

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
