from datetime import datetime, timedelta, timezone
from openai import AsyncOpenAI
from app.config import settings
from app.database import get_service_client

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def generate_embedding(text: str) -> list[float]:
    """Generate embedding vector using OpenAI text-embedding-3-small."""
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


async def store_item_embedding(item_id: str, text: str) -> None:
    """Generate and store embedding for a receipt item."""
    embedding = await generate_embedding(text)
    db = get_service_client()
    db.table("receipt_items").update({"embedding": embedding}).eq("id", item_id).execute()


async def get_relevant_context(user_id: str, query: str, history: list[dict] = None) -> dict:
    """Build context for chat RAG from user's data + store prices."""
    db = get_service_client()
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)

    # Current month receipts (with store and date) — only completed with real totals
    month_receipts = (
        db.table("receipts")
        .select("id, total_amount, store_name, purchased_at")
        .eq("user_id", user_id)
        .gte("purchased_at", month_start.isoformat())
        .gt("total_amount", 0)
        .order("purchased_at", desc=True)
        .execute()
    )
    month_data = month_receipts.data or []
    month_total = sum(r["total_amount"] for r in month_data)
    month_count = len(month_data)

    # Build receipt_id -> store_name mapping
    receipt_store: dict[str, str] = {}
    for r in month_data:
        receipt_store[r["id"]] = r["store_name"]

    # Previous month spending
    prev_receipts = (
        db.table("receipts")
        .select("total_amount")
        .eq("user_id", user_id)
        .gte("purchased_at", prev_month_start.isoformat())
        .lt("purchased_at", month_start.isoformat())
        .execute()
    )
    prev_total = sum(r["total_amount"] for r in (prev_receipts.data or []))

    # Store spending breakdown this month
    store_spending: dict[str, float] = {}
    store_counts: dict[str, int] = {}
    for r in month_data:
        s = r["store_name"]
        store_spending[s] = store_spending.get(s, 0) + r["total_amount"]
        store_counts[s] = store_counts.get(s, 0) + 1
    top_store = max(store_counts, key=store_counts.get) if store_counts else "N/A"

    store_summary = ", ".join(
        f"€{v:.2f} at {s}"
        for s, v in sorted(store_spending.items(), key=lambda x: -x[1])
    ) or "No spending this month."

    # Unique products count
    products = (
        db.table("receipt_items")
        .select("normalized_name")
        .eq("user_id", user_id)
        .execute()
    )
    unique_products = len(set(p["normalized_name"] for p in (products.data or [])))

    # Recent items — includes quantity and receipt_id for store lookup
    recent_items = (
        db.table("receipt_items")
        .select(
            "normalized_name, category, total_price, unit_price, "
            "quantity, receipt_id"
        )
        .eq("user_id", user_id)
        .gte("created_at", month_start.isoformat())
        .limit(200)
        .execute()
    )

    # Category summary
    items_summary = ""
    full_items_lines: list[str] = []
    if recent_items.data:
        by_cat: dict[str, dict] = {}
        for item in recent_items.data:
            cat = item["category"]
            if cat not in by_cat:
                by_cat[cat] = {"total": 0.0, "qty": 0.0}
            by_cat[cat]["total"] += item["total_price"]
            by_cat[cat]["qty"] += item.get("quantity") or 1

            # Full item line with store
            store = receipt_store.get(item.get("receipt_id", ""), "Unknown")
            qty = item.get("quantity") or 1
            full_items_lines.append(
                f"- {store} | {item['normalized_name']} | "
                f"qty: {qty} | €{item['total_price']:.2f}"
            )

        items_summary = "\n".join(
            f"- {cat}: €{v['total']:.2f} ({v['qty']:.0f} items)"
            for cat, v in sorted(by_cat.items(), key=lambda x: -x[1]["total"])
        )

    full_items_text = "\n".join(full_items_lines[:100]) or "No items this month."

    # Top 10 most purchased products (from user_product_patterns)
    top_products_text = ""
    favourite_categories_text = ""
    try:
        patterns = (
            db.table("user_product_patterns")
            .select(
                "normalized_name, category, purchase_count, "
                "avg_price, total_quantity"
            )
            .eq("user_id", user_id)
            .order("purchase_count", desc=True)
            .limit(10)
            .execute()
        )
        if patterns.data:
            lines = []
            cat_counts: dict[str, int] = {}
            for p in patterns.data:
                qty = p.get("total_quantity") or p["purchase_count"]
                lines.append(
                    f"- {p['normalized_name']}: bought {p['purchase_count']} times "
                    f"({qty:.0f} units), avg €{p['avg_price']:.2f}"
                )
                cat = p.get("category", "Other")
                cat_counts[cat] = cat_counts.get(cat, 0) + p["purchase_count"]
            top_products_text = "\n".join(lines)
            favourite_categories_text = ", ".join(
                sorted(cat_counts, key=cat_counts.get, reverse=True)[:5]
            )
    except Exception:
        pass

    # Price insights (reuse patterns data)
    price_insights = top_products_text or "No price insights available yet."

    # User profile name
    user_name = ""
    try:
        profile = (
            db.table("profiles")
            .select("full_name")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        if profile.data and profile.data.get("full_name"):
            user_name = profile.data["full_name"]
    except Exception:
        pass

    # SmartDocket savings (attributed savings from alerts)
    smartdocket_savings_total = 0.0
    smartdocket_savings_month = 0.0
    try:
        from app.services.attribution_service import (
            get_monthly_smartdocket_savings,
            get_total_smartdocket_savings,
        )

        smartdocket_savings_total = get_total_smartdocket_savings(
            db, user_id
        )
        smartdocket_savings_month = get_monthly_smartdocket_savings(
            db,
            user_id,
            month_start.isoformat(),
            now.isoformat(),
        )
    except Exception:
        pass

    # Fetch store prices for products mentioned in the query or conversation
    store_prices_text = "No specific product queried."
    try:
        import re as _re
        # Extract product keywords from query + recent history
        price_keywords = _extract_price_keywords(query, history or [])
        if price_keywords:
            price_lines = []
            for kw in price_keywords[:3]:  # Max 3 products to keep tokens low
                ilike = f"%{kw}%"
                prices_result = db.rpc(
                    "search_products",
                    {"p_query": ilike, "p_source": "leaflet", "p_limit": 15},
                ).execute()
                if prices_result.data:
                    # Filter with word boundary
                    kw_lower = kw.lower()
                    filtered = [
                        p for p in prices_result.data
                        if _re.search(r'\b' + _re.escape(kw_lower) + r'\b', p["product_name"].lower())
                    ]
                    # Deduplicate by store (cheapest per store)
                    by_store: dict[str, dict] = {}
                    for p in filtered:
                        s = p["store_name"]
                        if s not in by_store or p["unit_price"] < by_store[s]["unit_price"]:
                            by_store[s] = p
                    sorted_prices = sorted(by_store.values(), key=lambda x: x["unit_price"])
                    for p in sorted_prices[:5]:
                        promo = f" ({p.get('promotion_text')})" if p.get("promotion_text") else ""
                        price_lines.append(
                            f"  {p['store_name']}: {p['product_name']} — €{p['unit_price']:.2f}{promo}"
                        )
            if price_lines:
                store_prices_text = "\n".join(price_lines)
    except Exception:
        pass

    return {
        "user_name": user_name,
        "current_hour_utc": now.hour,
        "month_total": month_total,
        "month_receipts": month_count,
        "prev_month_total": prev_total,
        "top_store": top_store,
        "store_summary": store_summary,
        "full_items_this_month": full_items_text,
        "store_prices": store_prices_text,
    }


def _extract_price_keywords(query: str, history: list[dict]) -> list[str]:
    """Extract product names the user is asking about from query + conversation."""
    import re as _re
    keywords = []

    # Common grocery product words to look for
    grocery_words = {
        "milk", "bread", "butter", "cheese", "chicken", "beef", "pork", "eggs",
        "rice", "pasta", "yogurt", "yoghurt", "cream", "juice", "water",
        "coffee", "tea", "sugar", "flour", "oil", "cereal", "ham", "bacon",
        "sausage", "potato", "tomato", "onion", "apple", "banana", "orange",
    }

    # Check query for grocery words or multi-word product names
    q_lower = query.lower()
    for word in grocery_words:
        if _re.search(r'\b' + word + r'\b', q_lower):
            keywords.append(word)

    # If query is short (1-2 words), it might be a follow-up — check history
    if len(query.split()) <= 2 and not keywords and history:
        # Look through recent assistant messages for product mentions
        for msg in reversed(history[-4:]):
            if msg.get("role") == "assistant":
                content_lower = msg["content"].lower()
                for word in grocery_words:
                    if _re.search(r'\b' + word + r'\b', content_lower):
                        keywords.append(word)
                if keywords:
                    break

    return list(dict.fromkeys(keywords))[:3]  # Unique, max 3


async def batch_embed_products(batch_size: int = 100) -> int:
    """Generate embeddings for collective_prices products that don't have one.

    Uses OpenAI text-embedding-3-small ($0.02/1M tokens).
    ~3,700 products ≈ $0.004 total.
    """
    import logging
    log = logging.getLogger(__name__)
    db = get_service_client()

    # Get products without embeddings
    result = (
        db.table("collective_prices")
        .select("id, product_name, category")
        .eq("source", "leaflet")
        .is_("embedding", "null")
        .limit(batch_size)
        .execute()
    )

    if not result.data:
        return 0

    products = result.data
    texts = [
        f"{p['product_name']} {p.get('category', '')}"
        for p in products
    ]

    try:
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )

        updated = 0
        for i, emb_data in enumerate(response.data):
            try:
                db.table("collective_prices").update({
                    "embedding": emb_data.embedding,
                }).eq("id", products[i]["id"]).execute()
                updated += 1
            except Exception:
                pass

        log.info(f"Embedded {updated}/{len(products)} products")
        return updated

    except Exception as e:
        log.warning(f"Batch embedding failed: {e}")
        return 0


async def run_full_embedding() -> int:
    """Embed all products without embeddings. Run in batches."""
    total = 0
    for _ in range(50):  # Max 50 batches = 5000 products
        count = await batch_embed_products(100)
        if count == 0:
            break
        total += count
    return total


async def find_similar_products(
    query_text: str,
    threshold: float = 0.7,
    limit: int = 5,
) -> list[dict]:
    """Find similar products using vector similarity."""
    embedding = await generate_embedding(query_text)
    db = get_service_client()

    try:
        result = db.rpc("match_products", {
            "query_embedding": embedding,
            "match_threshold": threshold,
            "match_count": limit,
        }).execute()
        return result.data or []
    except Exception:
        return []
