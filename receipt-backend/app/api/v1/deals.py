"""Weekly deals endpoint — serves trending + personalised + golden deals."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.database import get_service_client
from app.services.cache_service import get_cache, set_cache
from app.utils.auth_utils import get_current_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("/weekly")
async def get_weekly_deals(user_id: str = Depends(get_current_user)):
    """Returns smart weekly deals: trending + personalised + golden (PRO).

    Free: 4 trending + 2 personal = 6 deals, refreshes every 4 days
    Pro:  4 trending + 6 personal + 3 golden = 13 deals, refreshes every 2 days
    """
    cache_key = f"weekly_deals:{user_id}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    db = get_service_client()
    now = datetime.now(timezone.utc).isoformat()

    # Get user plan
    try:
        profile = (
            db.table("profiles")
            .select("plan")
            .eq("id", user_id)
            .single()
            .execute()
        )
        plan = (profile.data or {}).get("plan", "free")
    except Exception:
        plan = "free"

    # Trending deals (global, same for everyone)
    trending = (
        db.table("weekly_deals")
        .select("*")
        .is_("user_id", "null")
        .eq("deal_type", "global")
        .gte("valid_until", now)
        .order("rank")
        .limit(4)
        .execute()
    )

    # Personal deals (for this user)
    personal_limit = 6 if plan == "pro" else 2
    personal = (
        db.table("weekly_deals")
        .select("*")
        .eq("user_id", user_id)
        .eq("deal_type", "personalised")
        .gte("valid_until", now)
        .order("rank")
        .limit(personal_limit)
        .execute()
    )

    # Golden deals (PRO only)
    golden_data = []
    if plan == "pro":
        golden = (
            db.table("weekly_deals")
            .select("*")
            .eq("user_id", user_id)
            .eq("deal_type", "golden")
            .gte("valid_until", now)
            .order("rank")
            .limit(3)
            .execute()
        )
        golden_data = golden.data or []

    response = {
        "plan": plan,
        "trending": trending.data or [],
        "personalised": personal.data or [],
        "golden": golden_data,
        "total": (
            len(trending.data or [])
            + len(personal.data or [])
            + len(golden_data)
        ),
        "refresh_days": 2 if plan == "pro" else 4,
    }

    # Cache for 1 hour
    set_cache(cache_key, response, ttl_seconds=3600)
    return response


@router.post("/generate")
async def trigger_deal_generation(user_id: str = Depends(get_current_user)):
    """Manually trigger deal generation (admin or debug)."""
    from app.workers.deals_worker import generate_all_deals

    # Run in background
    asyncio.create_task(generate_all_deals())
    return {"status": "started", "message": "Deal generation triggered"}


@router.get("/price-history/{product_key}")
async def get_price_history(
    product_key: str,
    weeks: int = 8,
    user_id: str = Depends(get_current_user),
):
    """Returns price history for a product across all stores."""
    cutoff = (
        datetime.now(timezone.utc) - timedelta(weeks=weeks)
    ).isoformat()

    db = get_service_client()
    history = (
        db.table("price_history")
        .select("store_name, unit_price, observed_at, source")
        .eq("product_key", product_key)
        .gte("observed_at", cutoff)
        .order("observed_at")
        .execute()
    )

    by_store: dict[str, list] = {}
    for row in history.data or []:
        store = row["store_name"]
        if store not in by_store:
            by_store[store] = []
        by_store[store].append(
            {
                "price": row["unit_price"],
                "date": row["observed_at"][:10],
                "source": row["source"],
            }
        )

    current = (
        db.table("collective_prices")
        .select("store_name, unit_price, is_on_offer")
        .eq("product_key", product_key)
        .gte("expires_at", datetime.now(timezone.utc).isoformat())
        .execute()
    )

    return {
        "product_key": product_key,
        "history": by_store,
        "current_prices": current.data or [],
        "weeks_shown": weeks,
    }


@router.get("/analytics/global")
async def get_global_analytics(
    user_id: str = Depends(get_current_user),
):
    """Returns global shopping insights."""
    db = get_service_client()

    hours = (
        db.table("shopping_hour_distribution").select("*").execute()
    )
    stores = db.table("store_popularity").select("*").execute()
    popular = (
        db.table("popular_products_this_month")
        .select(
            "normalized_name, category, "
            "purchase_count, unique_buyers"
        )
        .limit(20)
        .execute()
    )

    return {
        "peak_hours": hours.data or [],
        "store_ranking": stores.data or [],
        "popular_products": popular.data or [],
    }
