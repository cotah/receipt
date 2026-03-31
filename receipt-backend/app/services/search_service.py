"""Smart product search with grouping and AI alternatives.

Flow:
1. User searches "brioche"
2. smart_search() does ILIKE on product_name, groups same products across stores
3. find_alternatives() uses OpenAI to suggest cheaper similar products
"""

import logging
import re
from datetime import datetime, timezone

from openai import AsyncOpenAI

from app.config import settings
from app.database import get_service_client

log = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Store brand prefixes to strip for grouping
_STORE_BRANDS = {
    "supervalu", "tesco", "lidl", "aldi", "dunnes",
    "tesco finest", "tesco everyday value", "tesco organic",
    "supervalu signature tastes", "supervalu organic",
}

# Regex to strip size/weight/pack info
_SIZE_RE = re.compile(
    r"\s*\(?\s*\d+\s*[xX×]\s*\d+\s*(ml|g|kg|l|cl|oz|lb|pk)?\s*\)?"
    r"|\s*\(?\s*\d+\.?\d*\s*(ml|g|kg|l|cl|oz|lb|pk|pck|pack)\s*\)?"
    r"|\s*\d+\s*pack\b"
    r"|\s*\(\s*\d+[^)]*\)",
    re.IGNORECASE,
)


def _normalize_for_grouping(name: str) -> str:
    """Normalize a product name for grouping purposes.

    Strips store brands, size/weight, and normalises whitespace.
    'SuperValu Strawberries (325 g)' → 'strawberries'
    'Bundys Brioche Burger Buns 4 Pack (320 g)' → 'bundys brioche burger buns'
    """
    n = name.lower().strip()
    # Strip store brands (longest first to catch "tesco finest" before "tesco")
    for brand in sorted(_STORE_BRANDS, key=len, reverse=True):
        if n.startswith(brand + " "):
            n = n[len(brand):].strip()
            break
    # Strip size/weight info
    n = _SIZE_RE.sub("", n).strip()
    # Normalise whitespace
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _token_similarity(a: str, b: str) -> float:
    """Smart token similarity that prevents false matches on differentiated products.

    'chicken breast' vs 'chicken breast bites' → LOW (bites changes the product)
    'honey' vs 'honey biscuits' → LOW (biscuits is a different product)
    'white bread' vs 'bread white' → HIGH (same tokens)
    'brennans bread' vs 'bread' → MEDIUM (brand difference is ok)
    """
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b

    # Base Jaccard score
    jaccard = len(intersection) / len(union)

    # PENALTY: if one side has extra words that are "product differentiators"
    # These words fundamentally change what the product IS
    # "Chicken" + "Bites" = different product than "Chicken"
    differentiators = {
        "bites", "biscuit", "biscuits", "cake", "cakes", "sauce", "soup",
        "crisp", "crisps", "chip", "chips", "bar", "bars", "spread",
        "yoghurt", "yogurt", "drink", "juice", "jam", "paste", "powder",
        "roast", "roasted", "smoked", "dried", "frozen", "canned", "tinned",
        "organic", "mini", "snack", "snacks", "wrap", "wraps", "roll", "rolls",
        "flavour", "flavoured", "coated", "stuffed", "glazed", "pickled",
        "ice", "cream", "pudding", "pie", "tart", "crumble",
    }

    extra_a = tokens_a - tokens_b
    extra_b = tokens_b - tokens_a

    # If extra words include a differentiator → NOT the same product
    if extra_a & differentiators or extra_b & differentiators:
        return min(jaccard, 0.4)  # Cap at 0.4 so it never passes 0.6 threshold

    return jaccard


def _group_products(rows: list[dict]) -> list[dict]:
    """Group products that are likely the same item across stores.

    SIZE-AWARE: Products with different weights/sizes are NOT grouped together.
    e.g. "Honey 1kg" and "Honey 340g" stay separate because they're different products.

    Returns a list of product groups, each with store prices.
    """
    groups: list[dict] = []  # [{norm_name, display_name, weight_g, stores: [...]}]

    for row in rows:
        norm = _normalize_for_grouping(row["product_name"])
        weight_g = _extract_weight_grams(row["product_name"])
        store_entry = {
            "store_name": row["store_name"],
            "product_name": row["product_name"],
            "unit_price": float(row["unit_price"]),
            "is_on_offer": row.get("is_on_offer", False),
            "observed_at": row.get("observed_at", ""),
            "product_key": row.get("product_key", ""),
            "promotion_text": row.get("promotion_text"),
            "weight_g": weight_g,
        }

        # Try to find an existing group with similar normalised name
        matched = False
        for group in groups:
            sim = _token_similarity(norm, group["norm_name"])
            if sim >= 0.6:
                # SIZE CHECK: don't group products with significantly different weights
                g_weight = group.get("weight_g")
                if weight_g and g_weight:
                    # Both have weights — only group if within 30% of each other
                    ratio = max(weight_g, g_weight) / min(weight_g, g_weight)
                    if ratio > 1.3:
                        continue  # Different sizes → skip, try next group or create new
                elif (weight_g and not g_weight) or (g_weight and not weight_g):
                    # One has weight, other doesn't — check price ratio as proxy
                    existing_price = group["stores"][0]["unit_price"]
                    new_price = store_entry["unit_price"]
                    if existing_price > 0 and new_price > 0:
                        price_ratio = max(existing_price, new_price) / min(existing_price, new_price)
                        if price_ratio > 1.8:
                            continue  # Price too different → likely different sizes

                # Check this store isn't already in the group
                existing_stores = {s["store_name"] for s in group["stores"]}
                if store_entry["store_name"] not in existing_stores:
                    group["stores"].append(store_entry)
                elif store_entry["unit_price"] < min(
                    s["unit_price"]
                    for s in group["stores"]
                    if s["store_name"] == store_entry["store_name"]
                ):
                    # Replace with cheaper price from same store
                    group["stores"] = [
                        s
                        for s in group["stores"]
                        if s["store_name"] != store_entry["store_name"]
                    ] + [store_entry]
                matched = True
                break

        if not matched:
            groups.append({
                "norm_name": norm,
                "display_name": row["product_name"],
                "product_key": row.get("product_key", ""),
                "weight_g": weight_g,
                "stores": [store_entry],
            })

    # Sort stores within each group by price
    for group in groups:
        group["stores"].sort(key=lambda s: s["unit_price"])
        # Use the name from the cheapest store as display name
        if group["stores"]:
            group["display_name"] = group["stores"][0]["product_name"]

    # Sort groups: multi-store first, then by cheapest price
    groups.sort(
        key=lambda g: (-len(g["stores"]), g["stores"][0]["unit_price"]),
    )

    return groups


def _find_better_value_tip(group: dict, all_groups: list[dict]) -> dict | None:
    """Find a better-value alternative in a different size of the same product.

    e.g. "Honey 1kg @ €3.00 (€0.30/100g)" vs "Honey 500g @ €1.30 (€0.26/100g)"
    → "Buy 2x Honey 500g at Tesco (€2.60) instead of Honey 1kg (€3.00). Saves €0.40"
    """
    if not group.get("stores"):
        return None

    # Get this group's cheapest store + weight
    my_store = group["stores"][0]
    my_name = my_store.get("product_name", "")
    my_price = my_store["unit_price"]
    my_weight = _extract_weight_grams(my_name)
    if not my_weight or my_weight <= 0:
        return None

    my_ppu = my_price / my_weight  # price per gram

    # Get base product name (without size/brand)
    my_base = _normalize_for_grouping(my_name)
    if not my_base or len(my_base) < 2:
        return None

    best_tip = None
    best_saving = 0

    for other in all_groups:
        if other is group:
            continue
        if not other.get("stores"):
            continue

        other_store = other["stores"][0]
        other_name = other_store.get("product_name", "")
        other_price = other_store["unit_price"]
        other_weight = _extract_weight_grams(other_name)
        if not other_weight or other_weight <= 0:
            continue

        # Check it's the same base product (high similarity)
        other_base = _normalize_for_grouping(other_name)
        # Use raw Jaccard here (no differentiator penalty) since we already
        # know these are different sizes of possibly the same product
        tokens_a = set(my_base.split())
        tokens_b = set(other_base.split())
        if not tokens_a or not tokens_b:
            continue
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        sim = len(intersection) / len(union)
        if sim < 0.5:
            continue

        other_ppu = other_price / other_weight  # price per gram

        # How many of the other product do we need to match our weight?
        qty_needed = my_weight / other_weight
        # Only consider whole numbers (you can't buy half a jar)
        qty_int = round(qty_needed)
        if qty_int < 1 or abs(qty_int - qty_needed) > 0.3:
            continue  # Not a clean multiple (e.g., 1kg vs 300g = 3.33 → skip)

        total_cost = other_price * qty_int
        total_weight = other_weight * qty_int

        # Only suggest if the alternative covers at least 80% of the weight
        if total_weight < my_weight * 0.8:
            continue

        saving = my_price - total_cost
        if saving > 0.10 and saving > best_saving:
            best_saving = saving
            best_tip = {
                "product_name": other_name,
                "store_name": other_store["store_name"],
                "quantity": qty_int,
                "unit_price": other_price,
                "total_price": round(total_cost, 2),
                "saving": round(saving, 2),
                "message": f"Buy {qty_int}x {other_name} at {other_store['store_name']} (€{total_cost:.2f}) instead of {my_name} (€{my_price:.2f}). Saves €{saving:.2f}",
            }

    return best_tip


async def smart_search(query: str, limit: int = 30) -> dict:
    """Search products across all stores with intelligent grouping.

    Returns grouped results where the same product from different
    stores appears as one entry with multiple store prices.
    """
    if not query or len(query.strip()) < 2:
        return {"query": query, "results": [], "total": 0}

    db = get_service_client()
    now = datetime.now(timezone.utc)
    q = query.strip()

    # Build search: split query into words for multi-word ILIKE
    words = q.split()
    ilike_pattern = "%" + "%".join(words) + "%"

    try:
        result = db.rpc(
            "search_products",
            {
                "p_query": ilike_pattern,
                "p_source": "leaflet",
                "p_limit": limit * 3,
            },
        ).execute()
    except Exception as e:
        log.error("smart_search: query failed: %s", e)
        return {"query": query, "results": [], "total": 0}

    rows = result.data or []
    if not rows:
        return {"query": query, "results": [], "total": 0}

    # Filter: ensure search words appear as WHOLE words, not substrings
    # "apple" must match "Apple Juice" but NOT "Pineapple Juice"
    # "bread" must match "White Bread" but NOT "Breaded Chicken"
    import re
    search_words = [w.lower() for w in q.split() if len(w) >= 2]
    filtered_rows = []
    for row in rows:
        name_lower = row["product_name"].lower()
        match = True
        for sw in search_words:
            # Use regex word boundary: \b matches start/end of word
            if not re.search(r'\b' + re.escape(sw) + r'\b', name_lower):
                match = False
                break
        if match:
            filtered_rows.append(row)

    rows = filtered_rows
    if not rows:
        return {"query": query, "results": [], "total": 0}

    # Group products
    groups = _group_products(rows)

    # Format response
    results = []
    for group in groups[:limit]:
        cheapest = group["stores"][0]
        most_expensive = group["stores"][-1] if len(group["stores"]) > 1 else None
        saving = (
            round(most_expensive["unit_price"] - cheapest["unit_price"], 2)
            if most_expensive and most_expensive["unit_price"] > cheapest["unit_price"]
            else None
        )

        stores = []
        # Reference weight: use the heaviest in the group for comparison
        ref_weight = group.get("weight_g")
        all_weights = [s.get("weight_g") for s in group["stores"] if s.get("weight_g")]
        max_weight = max(all_weights) if all_weights else None

        for i, s in enumerate(group["stores"]):
            pup = _per_unit_price(s["unit_price"], s["product_name"])
            entry = {
                "store_name": s["store_name"],
                "product_name": s["product_name"],
                "unit_price": s["unit_price"],
                "is_on_offer": s["is_on_offer"],
                "is_cheapest": i == 0 and len(group["stores"]) > 1,
                "price_per_unit": round(pup * 100, 2) if pup else None,
                "price_per_unit_label": "per 100g" if pup else None,
                "promotion_text": s.get("promotion_text"),
                "weight_note": None,
            }
            # Add weight difference note if products vary in size
            s_weight = s.get("weight_g")
            if s_weight and max_weight and abs(s_weight - max_weight) > 10:
                diff = max_weight - s_weight
                if diff > 0:
                    if diff >= 1000:
                        entry["weight_note"] = f"{diff/1000:.1f}kg less"
                    else:
                        entry["weight_note"] = f"{int(diff)}g less"
            stores.append(entry)

        results.append({
            "display_name": group["display_name"],
            "product_key": group["product_key"],
            "stores": stores,
            "store_count": len(stores),
            "cheapest_price": cheapest["unit_price"],
            "cheapest_store": cheapest["store_name"],
            "potential_saving": saving,
        })

    # --- Better-value tips across different sizes ---
    # Compare groups that are the same base product but different sizes
    for group in results:
        tip = _find_better_value_tip(group, results)
        if tip:
            group["value_tip"] = tip

    return {
        "query": query,
        "results": results,
        "total": len(results),
    }


async def find_alternatives(
    product_name: str, limit: int = 5, exclude_keys: list[str] | None = None,
) -> list[dict]:
    """Use OpenAI to find the same product at different stores/sizes.

    1. Asks AI to generate search terms for the SAME product
    2. Searches the DB for those terms
    3. Filters with AI verification
    4. Excludes the product already being viewed
    """
    if not settings.OPENAI_API_KEY or not product_name:
        return []

    db = get_service_client()
    now = datetime.now(timezone.utc)

    try:
        # Step 1: Ask OpenAI for alternative product search terms
        response = await client.chat.completions.create(
            model="gpt-5.4-nano",
            temperature=0.1,
            max_completion_tokens=200,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a grocery product search expert for Irish supermarkets "
                        "(Tesco, SuperValu, Lidl, Aldi, Dunnes).\n\n"
                        "Each store has its OWN brand products (Tesco Everyday, Lidl Cien, Aldi Brooklea, etc).\n"
                        "The SAME product exists across stores under different brand names.\n\n"
                        "STRICT RULES:\n"
                        "- Given a product, return search terms for the EXACT SAME type of product\n"
                        "- ANY brand is OK — store brands, name brands, generic versions\n"
                        "- Different sizes are OK (500g, 1L, 2-pack, etc)\n"
                        "- NEVER suggest a DIFFERENT product category\n\n"
                        "CORRECT examples:\n"
                        "- 'Apple Juice 1L' → 'apple juice', 'pressed apple juice', 'pure apple juice'\n"
                        "- 'Chicken Breast Fillets 500g' → 'chicken breast', 'chicken breast fillets', 'chicken fillet'\n"
                        "- 'Semi Skimmed Milk 2L' → 'semi skimmed milk', 'low fat milk', 'milk 2l'\n\n"
                        "WRONG examples (NEVER do this):\n"
                        "- 'Apple Juice' → 'orange juice' (DIFFERENT FRUIT!)\n"
                        "- 'Chicken Breast' → 'chicken thighs' (DIFFERENT CUT!)\n"
                        "- 'Milk' → 'oat drink' (DIFFERENT PRODUCT!)\n\n"
                        "Return 2-4 SHORT search terms (1-3 words each), one per line, no numbering."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Product: {product_name}",
                },
            ],
        )

        ai_text = response.choices[0].message.content or ""
        search_terms = [
            line.strip()
            for line in ai_text.strip().split("\n")
            if line.strip() and len(line.strip()) >= 2
        ]
        log.info(
            "find_alternatives: AI suggested terms for '%s': %s",
            product_name, search_terms,
        )

    except Exception as e:
        log.error("find_alternatives: OpenAI error: %s", e)
        return []

    if not search_terms:
        return []

    # Step 2: Search DB for each term and collect results
    all_alternatives: list[dict] = []
    seen_keys: set[str] = set()
    # Pre-populate seen_keys with excluded products (the one being viewed)
    if exclude_keys:
        seen_keys.update(exclude_keys)

    for term in search_terms[:5]:
        try:
            words = term.split()
            pattern = "%" + "%".join(words) + "%"
            result = db.rpc(
                "search_products",
                {
                    "p_query": pattern,
                    "p_source": "leaflet",
                    "p_limit": 5,
                },
            ).execute()
            for row in result.data or []:
                key = row["product_key"]
                if key not in seen_keys:
                    # Validate: must be same type of product
                    norm_original = _normalize_for_grouping(product_name)
                    norm_result = _normalize_for_grouping(row["product_name"])
                    # Check core words overlap
                    orig_words = set(norm_original.split())
                    result_words = set(norm_result.split())
                    # At least one important word must match
                    important_overlap = orig_words & result_words
                    if not important_overlap:
                        continue
                    
                    seen_keys.add(key)
                    pup = _per_unit_price(float(row["unit_price"]), row["product_name"])
                    all_alternatives.append({
                        "product_name": row["product_name"],
                        "product_key": key,
                        "store_name": row["store_name"],
                        "unit_price": float(row["unit_price"]),
                        "is_on_offer": row.get("is_on_offer", False),
                        "search_term": term,
                        "price_per_100": round(pup * 100, 2) if pup else None,
                    })
        except Exception as e:
            log.warning(
                "find_alternatives: search for '%s' failed: %s", term, e
            )

    # Sort by price and return top alternatives
    all_alternatives.sort(key=lambda x: x["unit_price"])
    candidates = all_alternatives[:limit * 2]  # Get extra for AI filtering

    if not candidates:
        return []

    # AI VERIFICATION — confirm each alternative is the EXACT SAME product type
    try:
        pairs = []
        for i, alt in enumerate(candidates):
            pairs.append(f'{i+1}. "{product_name}" vs "{alt["product_name"]}"')

        verify_prompt = f"""You are a deterministic grocery product comparator. Your sole function is to decide whether pairs of supermarket products are the SAME product type. You operate inside a production price-comparison pipeline — your output is parsed programmatically.

ABSOLUTE OUTPUT CONTRACT:
For each numbered pair, return EXACTLY: the pair number, a period, a space, then YES or NO.
One pair per line. No blank lines. Zero text before or after. No explanations. No reasoning.

THE CORE QUESTION:
"Would a consumer doing a weekly grocery shop consider these interchangeable?"
YES = same product type, same form, same essential variant. Buying one instead of the other satisfies the same meal/recipe need.
NO = different product type, different animal cut, different fruit/vegetable, different form, or different core function.

THE 8 MATCHING LAWS:

LAW 1 — IGNORE THESE (never affect answer): Brand name, pack size/weight/volume, price, organic/non-organic, free range/standard, fat level (whole/low fat/skimmed milk = all milk), salt modifier (salted/unsalted butter = butter), packaging format, "fresh" label, country of origin, sliced/unsliced, marketing words (premium, finest, classic).

LAW 2 — CORE PRODUCT IDENTITY MUST MATCH: Extract core product noun(s). "Chicken Breast Fillets" and "Chicken Breast 1kg" = both chicken breast = YES. "Chicken Breast" and "Chicken Thighs" = different cuts = NO. "Apple Juice" and "Orange Juice" = different fruit = NO.

LAW 3 — CRITICAL DIFFERENTIATORS (any difference = NO): Animal species (chicken/turkey/beef/pork/lamb/salmon/cod). Meat cut (breast/thigh/leg/wing/mince/fillet/steak/diced/drumstick/loin/chop). Fruit/veg type (apple/orange/banana/strawberry/tomato/potato/onion). Grain type (white rice/brown rice/pasta/noodles). Bread type (white/brown/sourdough/wholemeal/wrap/pitta/tortilla). Cheese type (cheddar/mozzarella/brie/feta/cream cheese). Drink base (milk/oat drink/soy drink/juice/water/cola). Juice fruit (apple/orange/cranberry/pineapple). Flavour (salt&vinegar vs cheese&onion crisps, strawberry vs vanilla yoghurt). Product form (fresh/frozen/tinned/dried/smoked). Product function (butter/margarine, sugar/sweetener). Preparation state (raw vs cooked chicken, fresh vs dried pasta).

LAW 4 — SUB-VARIANTS ARE SAME PRODUCT: Mature Cheddar vs Mild Cheddar = YES. Red Onions vs White Onions = YES. Cherry Tomatoes vs Vine Tomatoes = YES. Penne vs Fusilli = YES (both pasta). Whole Milk vs Semi-Skimmed = YES. Greek Yoghurt vs Natural Yoghurt = YES. Salted vs Unsalted Butter = YES. Still vs Sparkling Water = YES. Back Rashers vs Streaky Rashers = YES.

LAW 5 — FORM BOUNDARY (different form = NO): Fresh vs Frozen = NO. Fresh vs Tinned = NO. Fresh vs Smoked = NO. Block Cheese vs Grated Cheese = NO. Whole Chicken vs Chicken Breast = NO. EXCEPTION: pre-packed vs loose = YES, sliced vs unsliced = YES, fresh OJ vs from-concentrate OJ = YES.

LAW 6 — COMPOSITE PRODUCTS MATCH ONLY IF SAME RECIPE: Margherita Pizza vs Margherita Pizza = YES. Margherita vs Pepperoni = NO. Chicken Curry vs Beef Curry = NO. Vegetable Soup vs Chicken Soup = NO.

LAW 7 — AMBIGUITY: "Chicken" alone vs "Chicken Breast" = NO (vague vs specific). "Mince" alone = assume beef mince. "Sausages" alone = assume pork. "Bread" alone vs "White Bread" = NO. Both equally vague ("Cheese" vs "Cheese") = YES.

LAW 8 — FINAL GATE: "If I sent someone to buy Product A and they came back with Product B, would I send them back?" Accept = YES. Send back = NO. When uncertain, default to NO.

{chr(10).join(pairs)}"""

        response = await client.chat.completions.create(
            model="gpt-5.4-nano",
            temperature=0,
            max_completion_tokens=200,
            messages=[{"role": "user", "content": verify_prompt}],
        )
        answer = response.choices[0].message.content.strip()

        verified = []
        for line in answer.split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split(".", 1)
            if len(parts) == 2:
                try:
                    idx = int(parts[0].strip()) - 1
                    if "YES" in parts[1].upper() and 0 <= idx < len(candidates):
                        verified.append(candidates[idx])
                except (ValueError, IndexError):
                    pass

        log.info(
            "find_alternatives: AI verified %d/%d for '%s'",
            len(verified), len(candidates), product_name,
        )
        return verified[:limit]

    except Exception as e:
        log.warning("find_alternatives: AI verify failed: %s", e)
        # On failure, return nothing — better empty than wrong
        return []


# Weight/size extraction for comparing like-for-like
_WEIGHT_RE = re.compile(
    r"(\d+\.?\d*)\s*(kg|g|ml|l|cl|oz|lb|litre|liter)\b",
    re.IGNORECASE,
)

_PACK_RE = re.compile(
    r"(\d+)\s*(?:x|×|pk|pack)\s*(?:(\d+\.?\d*)\s*(g|ml|kg|l|cl))?",
    re.IGNORECASE,
)


def _extract_weight_grams(name: str) -> float | None:
    """Extract total weight from product name and normalize to grams.
    
    Handles multi-packs: '6 x 330ml' = 1980g, '2 Pack 500g' = 1000g
    Returns None if no weight found.
    """
    # Check for multi-pack first: "6 x 330ml", "4 pack 125g"
    pack_match = _PACK_RE.search(name)
    if pack_match and pack_match.group(2):
        count = int(pack_match.group(1))
        value = float(pack_match.group(2))
        unit = pack_match.group(3).lower()
        per_item = _normalize_to_grams(value, unit)
        if per_item is not None:
            return count * per_item
    
    # Single item weight
    match = _WEIGHT_RE.search(name)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower()
    return _normalize_to_grams(value, unit)


def _normalize_to_grams(value: float, unit: str) -> float | None:
    """Convert a value+unit to grams (or ml for liquids)."""
    if unit in ("kg",):
        return value * 1000
    if unit in ("g",):
        return value
    if unit in ("l", "litre", "liter"):
        return value * 1000
    if unit in ("ml",):
        return value
    if unit in ("cl",):
        return value * 10
    if unit in ("lb",):
        return value * 453.6
    if unit in ("oz",):
        return value * 28.35
    return None


def _per_unit_price(price: float, name: str) -> float | None:
    """Calculate price per gram/ml for comparison.
    
    This enables comparing: 1kg @ €10 vs 500g @ €4 (€0.01/g vs €0.008/g)
    """
    weight = _extract_weight_grams(name)
    if weight and weight > 0:
        return price / weight
    return None


def are_comparable_products(name_a: str, name_b: str, price_a: float, price_b: float) -> bool:
    """Check if two products are genuinely comparable (same product, similar value).
    
    Rules:
    1. Name similarity must be >= 0.35 (core words overlap)
    2. If both have weights, compare per-unit price (allows 2x500g vs 1kg)
    3. If only ONE has weight + price diff > 1.5x → NOT comparable
       (e.g. "Chicken Breast" €10.49 vs "Chicken Breast 500g" €4.99 = different sizes)
    4. If neither has weight, price ratio must be < 2.0x
    """
    # Name similarity first
    norm_a = _normalize_for_grouping(name_a)
    norm_b = _normalize_for_grouping(name_b)
    sim = _token_similarity(norm_a, norm_b)
    if sim < 0.35:
        return False
    
    w_a = _extract_weight_grams(name_a)
    w_b = _extract_weight_grams(name_b)
    
    # CASE 1: Both have weights → compare per-unit price
    if w_a and w_b:
        pup_a = price_a / w_a
        pup_b = price_b / w_b
        pup_ratio = max(pup_a, pup_b) / min(pup_a, pup_b) if min(pup_a, pup_b) > 0 else 99
        if pup_ratio > 2.5:
            return False
        return True
    
    # CASE 2: Only ONE has weight → can NOT compare reliably
    # "Chicken Breast Fillets" €10.49 (unknown size) vs "375g" €7.39
    # Could be 1kg vs 375g = totally different per-unit price
    # Until user confirms weight, reject these matches
    if (w_a and not w_b) or (w_b and not w_a):
        return False
    
    # CASE 3: Neither has weight → strict price ratio
    if price_a > 0 and price_b > 0:
        ratio = max(price_a, price_b) / min(price_a, price_b)
        if ratio > 2.0:
            return False
    
    return True
