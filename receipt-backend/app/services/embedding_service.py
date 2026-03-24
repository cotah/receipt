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

    # Current month spending
    month_receipts = (
        db.table("receipts")
        .select("total_amount, store_name")
        .eq("user_id", user_id)
        .gte("purchased_at", month_start.isoformat())
        .execute()
    )
    month_data = month_receipts.data or []
    month_total = sum(r["total_amount"] for r in month_data)
    month_count = len(month_data)

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

    # Top store
    store_counts: dict[str, int] = {}
    for r in month_data:
        store_counts[r["store_name"]] = store_counts.get(r["store_name"], 0) + 1
    top_store = max(store_counts, key=store_counts.get) if store_counts else "N/A"

    # Unique products count
    products = (
        db.table("receipt_items")
        .select("normalized_name")
        .eq("user_id", user_id)
        .execute()
    )
    unique_products = len(set(p["normalized_name"] for p in (products.data or [])))

    # Recent items summary (last 30 days)
    recent_items = (
        db.table("receipt_items")
        .select("normalized_name, category, total_price, unit_price")
        .eq("user_id", user_id)
        .gte("created_at", (now - timedelta(days=30)).isoformat())
        .limit(50)
        .execute()
    )
    items_summary = ""
    if recent_items.data:
        by_cat: dict[str, float] = {}
        for item in recent_items.data:
            cat = item["category"]
            by_cat[cat] = by_cat.get(cat, 0) + item["total_price"]
        items_summary = "\n".join(
            f"- {cat}: €{total:.2f}" for cat, total in sorted(by_cat.items(), key=lambda x: -x[1])
        )

    # Price insights
    price_insights = "No price insights available yet."
    try:
        patterns = (
            db.table("user_product_patterns")
            .select("*")
            .eq("user_id", user_id)
            .order("purchase_count", desc=True)
            .limit(5)
            .execute()
        )
        if patterns.data:
            lines = []
            for p in patterns.data:
                lines.append(
                    f"- {p['normalized_name']}: bought {p['purchase_count']} times, "
                    f"avg €{p['avg_price']:.2f}"
                )
            price_insights = "\n".join(lines)
    except Exception:
        pass

    return {
        "month_total": month_total,
        "month_receipts": month_count,
        "prev_month_total": prev_total,
        "top_store": top_store,
        "product_count": unique_products,
        "recent_items_summary": items_summary or "No recent purchases.",
        "price_insights": price_insights,
    }
