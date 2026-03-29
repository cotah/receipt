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
    """Simple token overlap similarity (Jaccard) between two normalised names."""
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _group_products(rows: list[dict]) -> list[dict]:
    """Group products that are likely the same item across stores.

    Returns a list of product groups, each with store prices.
    """
    groups: list[dict] = []  # [{norm_name, display_name, stores: [...]}]

    for row in rows:
        norm = _normalize_for_grouping(row["product_name"])
        store_entry = {
            "store_name": row["store_name"],
            "product_name": row["product_name"],
            "unit_price": float(row["unit_price"]),
            "is_on_offer": row.get("is_on_offer", False),
            "observed_at": row.get("observed_at", ""),
            "product_key": row.get("product_key", ""),
        }

        # Try to find an existing group with similar normalised name
        matched = False
        for group in groups:
            sim = _token_similarity(norm, group["norm_name"])
            if sim >= 0.6:
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
    search_words = [w.lower() for w in q.split() if len(w) >= 2]
    filtered_rows = []
    for row in rows:
        name_lower = " " + row["product_name"].lower() + " "
        match = True
        for sw in search_words:
            # Check word exists with word boundary (space, start, or punctuation before it)
            if f" {sw}" not in name_lower and not name_lower.lstrip().startswith(sw):
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
        for i, s in enumerate(group["stores"]):
            pup = _per_unit_price(s["unit_price"], s["product_name"])
            stores.append({
                "store_name": s["store_name"],
                "product_name": s["product_name"],
                "unit_price": s["unit_price"],
                "is_on_offer": s["is_on_offer"],
                "is_cheapest": i == 0 and len(group["stores"]) > 1,
                "price_per_unit": round(pup * 100, 2) if pup else None,  # cents per 100g/ml
                "price_per_unit_label": "per 100g" if pup else None,
            })

        results.append({
            "display_name": group["display_name"],
            "product_key": group["product_key"],
            "stores": stores,
            "store_count": len(stores),
            "cheapest_price": cheapest["unit_price"],
            "cheapest_store": cheapest["store_name"],
            "potential_saving": saving,
        })

    return {
        "query": query,
        "results": results,
        "total": len(results),
    }


async def find_alternatives(
    product_name: str, limit: int = 5
) -> list[dict]:
    """Use OpenAI to find cheaper alternative products in the database.

    1. Asks AI to generate search terms for similar/alternative products
    2. Searches the DB for those terms
    3. Returns cheaper alternatives grouped by store
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

        verify_prompt = f"""Are these the EXACT SAME type of grocery product? Only different brand/size is OK.

STRICT: Same product type, same cut, same form = YES. Different type/cut/form = NO.
- "Chicken Breast 500g" vs "Chicken Breast Fillets 1kg" = YES (same cut)
- "Chicken Breast" vs "Chicken Thighs" = NO (different cut!)
- "Apple Juice 1L" vs "Pure Apple Juice 500ml" = YES (same juice)
- "Apple Juice" vs "Orange Juice" = NO (different fruit!)
- "Milk 2L" vs "Low Fat Milk 1L" = YES (same product)
- "Milk" vs "Oat Drink" = NO (different product!)

Reply ONLY with number and YES/NO:

{chr(10).join(pairs)}"""

        response = await client.chat.completions.create(
            model="gpt-4.1-nano",
            temperature=0,
            max_completion_tokens=150,
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
    1. Name similarity must be >= 0.4 (core words overlap)
    2. If both have weights, compare per-unit price (allows 2x500g vs 1kg)
    3. If no weights, price ratio must be < 2.5x
    """
    # Name similarity first
    norm_a = _normalize_for_grouping(name_a)
    norm_b = _normalize_for_grouping(name_b)
    sim = _token_similarity(norm_a, norm_b)
    if sim < 0.35:
        return False
    
    # If both have weights, use per-unit price comparison
    # This handles: "Chicken Breast 1kg €10" vs "Chicken Breast 500g €4.50"
    pup_a = _per_unit_price(price_a, name_a)
    pup_b = _per_unit_price(price_b, name_b)
    
    if pup_a and pup_b:
        # Compare per-gram/ml price — allows up to 2x difference
        pup_ratio = max(pup_a, pup_b) / min(pup_a, pup_b)
        if pup_ratio > 2.5:
            return False
        return True
    
    # No weight info — fall back to absolute price ratio
    if price_a > 0 and price_b > 0:
        ratio = max(price_a, price_b) / min(price_a, price_b)
        if ratio > 2.5:
            return False
    
    return True
