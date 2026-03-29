import logging
from datetime import datetime, timedelta, timezone

from supabase import Client

from app.utils.price_utils import get_ttl_days
from app.utils.text_utils import generate_product_key

log = logging.getLogger(__name__)


async def record_shopping_analytics(
    db: Client,
    receipt_id: str,
    user_id: str,
    store_name: str,
    purchased_at: datetime,
    total_amount: float,
    items_count: int,
) -> None:
    """Record shopping behaviour analytics — time, store, spend."""
    try:
        db.table("shopping_analytics").upsert(
            {
                "receipt_id": receipt_id,
                "user_id": user_id,
                "store_name": store_name,
                "purchased_at": purchased_at.isoformat()
                if isinstance(purchased_at, datetime)
                else str(purchased_at),
                "total_amount": total_amount,
                "items_count": items_count,
            },
            on_conflict="receipt_id",
        ).execute()
    except Exception as e:
        log.warning("shopping_analytics insert failed: %s", e)


async def record_price_history(
    db: Client,
    product_key: str,
    product_name: str,
    store_name: str,
    unit_price: float,
    source: str,
    observed_at: datetime,
) -> None:
    """Always record a price observation in history."""
    try:
        db.table("price_history").insert(
            {
                "product_key": product_key,
                "product_name": product_name,
                "store_name": store_name,
                "unit_price": unit_price,
                "source": source,
                "observed_at": observed_at.isoformat()
                if isinstance(observed_at, datetime)
                else str(observed_at),
            }
        ).execute()
    except Exception as e:
        log.warning("price_history insert failed: %s", e)


async def contribute_anonymous_price(
    db: Client,
    item_data: dict,
    store_name: str,
    store_branch: str | None,
    home_area: str | None,
    observed_at: datetime,
) -> None:
    """Contribute price — only updates collective_prices if new price is lower."""
    category = item_data.get("category", "Other")
    ttl_days = get_ttl_days(category)
    product_key = generate_product_key(
        item_data["normalized_name"], item_data.get("unit")
    )
    expires_at = observed_at + timedelta(days=ttl_days)

    try:
        db.rpc(
            "upsert_collective_price",
            {
                "p_product_key": product_key,
                "p_product_name": item_data["normalized_name"],
                "p_category": category,
                "p_store_name": store_name,
                "p_store_branch": store_branch,
                "p_home_area": home_area,
                "p_unit_price": item_data["unit_price"],
                "p_unit": item_data.get("unit"),
                "p_is_on_offer": item_data.get("is_on_offer", False),
                "p_source": "receipt",
                "p_observed_at": observed_at.isoformat(),
                "p_expires_at": expires_at.isoformat(),
            },
        ).execute()
    except Exception as e:
        log.warning("upsert_collective_price RPC failed: %s", e)

    # Always record in price history
    await record_price_history(
        db,
        product_key=product_key,
        product_name=item_data["normalized_name"],
        store_name=store_name,
        unit_price=item_data["unit_price"],
        source="receipt",
        observed_at=observed_at,
    )


async def get_best_price(
    db: Client, product_key: str, area: str | None = None
) -> dict | None:
    """Get cheapest current price for a product."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        query = (
            db.table("collective_prices")
            .select("product_key, product_name, store_name, store_branch, unit_price, category, is_on_offer, source, observed_at, expires_at, home_area")
            .ilike("product_key", f"{product_key}%")
            .gte("expires_at", now)
            .order("unit_price")
            .limit(1)
        )
        if area:
            query = query.eq("home_area", area)
        result = query.execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


async def compare_prices(
    db: Client, product: str, area: str | None = None
) -> list[dict]:
    """Get all store prices for a product, sorted cheapest first."""
    now = datetime.now(timezone.utc).isoformat()
    product_key = generate_product_key(product)

    try:
        query = (
            db.table("collective_prices")
            .select("product_key, product_name, store_name, store_branch, unit_price, category, is_on_offer, source, observed_at, expires_at, home_area")
            .ilike("product_key", f"{product_key}%")
            .gte("expires_at", now)
            .order("unit_price")
        )
        if area:
            query = query.eq("home_area", area)
        result = query.execute()
        return result.data or []
    except Exception:
        return []


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
