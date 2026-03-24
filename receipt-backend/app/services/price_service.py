from datetime import datetime, timedelta, timezone
from supabase import Client
from app.utils.price_utils import get_ttl_days
from app.utils.text_utils import generate_product_key


async def contribute_anonymous_price(
    db: Client,
    item_data: dict,
    store_name: str,
    store_branch: str | None,
    home_area: str | None,
    observed_at: datetime,
) -> None:
    """Contribute a price to the collective bank — completely anonymous."""
    category = item_data.get("category", "Other")
    ttl_days = get_ttl_days(category)
    product_key = generate_product_key(
        item_data["normalized_name"], item_data.get("unit")
    )
    expires_at = observed_at + timedelta(days=ttl_days)

    # Check if similar price already exists recently
    existing = (
        db.table("collective_prices")
        .select("id, confirmation_count")
        .eq("product_key", product_key)
        .eq("store_name", store_name)
        .eq("unit_price", item_data["unit_price"])
        .gte("observed_at", (observed_at - timedelta(days=1)).isoformat())
        .limit(1)
        .execute()
    )

    if existing.data:
        # Increment confirmation
        row = existing.data[0]
        db.table("collective_prices").update(
            {
                "confirmation_count": row["confirmation_count"] + 1,
                "observed_at": observed_at.isoformat(),
                "expires_at": expires_at.isoformat(),
            }
        ).eq("id", row["id"]).execute()
    else:
        db.table("collective_prices").insert(
            {
                "product_key": product_key,
                "product_name": item_data["normalized_name"],
                "category": category,
                "store_name": store_name,
                "store_branch": store_branch,
                "home_area": home_area,
                "unit_price": item_data["unit_price"],
                "unit": item_data.get("unit"),
                "is_on_offer": item_data.get("is_on_offer", False),
                "source": "receipt",
                "observed_at": observed_at.isoformat(),
                "expires_at": expires_at.isoformat(),
            }
        ).execute()


async def get_best_price(
    db: Client, product_key: str, area: str | None = None
) -> dict | None:
    """Get cheapest current price for a product."""
    now = datetime.now(timezone.utc).isoformat()
    query = (
        db.table("collective_prices")
        .select("*")
        .eq("product_key", product_key)
        .gte("expires_at", now)
        .order("unit_price")
        .limit(1)
    )
    if area:
        query = query.eq("home_area", area)
    result = query.execute()
    return result.data[0] if result.data else None


async def compare_prices(
    db: Client, product: str, area: str | None = None
) -> list[dict]:
    """Get all store prices for a product, sorted cheapest first."""
    now = datetime.now(timezone.utc).isoformat()
    product_key = generate_product_key(product)

    query = (
        db.table("collective_prices")
        .select("*")
        .eq("product_key", product_key)
        .gte("expires_at", now)
        .order("unit_price")
    )
    if area:
        query = query.eq("home_area", area)
    result = query.execute()
    return result.data or []


async def cleanup_expired_prices(db: Client) -> int:
    """Delete all expired price entries. Returns count deleted."""
    now = datetime.now(timezone.utc).isoformat()
    result = (
        db.table("collective_prices")
        .delete()
        .lt("expires_at", now)
        .execute()
    )
    return len(result.data) if result.data else 0
