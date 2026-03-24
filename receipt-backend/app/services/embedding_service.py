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


async def get_relevant_context(user_id: str, query: str) -> dict:
    """Build context for chat RAG from user's data."""
    db = get_service_client()
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)

    # Current month receipts (with store and date)
    month_receipts = (
        db.table("receipts")
        .select("id, total_amount, store_name, purchased_at")
        .eq("user_id", user_id)
        .gte("purchased_at", month_start.isoformat())
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
            .single()
            .execute()
        )
        if profile.data and profile.data.get("full_name"):
            user_name = profile.data["full_name"]
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
        "product_count": unique_products,
        "recent_items_summary": items_summary or "No recent purchases.",
        "full_items_this_month": full_items_text,
        "price_insights": price_insights,
        "top_products": top_products_text or "No purchase history yet.",
        "favourite_categories": favourite_categories_text or "N/A",
    }
