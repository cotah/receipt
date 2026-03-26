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
        result = (
            db.table("collective_prices")
            .select(
                "product_name, product_key, store_name, "
                "unit_price, is_on_offer, observed_at"
            )
            .eq("source", "leaflet")
            .gte("expires_at", now.isoformat())
            .ilike("product_name", ilike_pattern)
            .order("unit_price")
            .limit(limit * 3)  # fetch extra for grouping
            .execute()
        )
    except Exception as e:
        log.error("smart_search: query failed: %s", e)
        return {"query": query, "results": [], "total": 0}

    rows = result.data or []
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
            stores.append({
                "store_name": s["store_name"],
                "product_name": s["product_name"],
                "unit_price": s["unit_price"],
                "is_on_offer": s["is_on_offer"],
                "is_cheapest": i == 0 and len(group["stores"]) > 1,
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
            temperature=0.3,
            max_completion_tokens=200,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a grocery product expert for Irish supermarkets "
                        "(Tesco, SuperValu, Lidl, Aldi, Dunnes). "
                        "Given a product name, suggest 3-5 SHORT search terms "
                        "(1-3 words each) for similar/alternative products that "
                        "a budget-conscious shopper might consider instead. "
                        "Focus on store-brand alternatives, similar products from "
                        "different brands, and generic versions. "
                        "Return ONLY the search terms, one per line, no numbering."
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
            result = (
                db.table("collective_prices")
                .select(
                    "product_name, product_key, store_name, "
                    "unit_price, is_on_offer"
                )
                .eq("source", "leaflet")
                .gte("expires_at", now.isoformat())
                .ilike("product_name", pattern)
                .order("unit_price")
                .limit(5)
                .execute()
            )
            for row in result.data or []:
                key = row["product_key"]
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_alternatives.append({
                        "product_name": row["product_name"],
                        "product_key": key,
                        "store_name": row["store_name"],
                        "unit_price": float(row["unit_price"]),
                        "is_on_offer": row.get("is_on_offer", False),
                        "search_term": term,
                    })
        except Exception as e:
            log.warning(
                "find_alternatives: search for '%s' failed: %s", term, e
            )

    # Sort by price and return top alternatives
    all_alternatives.sort(key=lambda x: x["unit_price"])
    return all_alternatives[:limit]
