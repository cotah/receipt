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

    Free: 8 trending + 2 personal + 0 golden = 10 deals
    Pro:  6 trending + 4 personal + 2 golden + seasonal = 12+ deals
    """
    cache_key = f"weekly_deals:{user_id}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    db = get_service_client()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # Get user plan
    try:
        profile = (
            db.table("profiles")
            .select("plan, plan_expires_at")
            .eq("id", user_id)
            .single()
            .execute()
        )
        from app.utils.plan_utils import is_pro
        plan = "pro" if is_pro(profile.data or {}) else "free"
    except Exception:
        plan = "free"

    # Deal counts based on plan
    trending_limit = 6 if plan == "pro" else 8
    personal_limit = 4 if plan == "pro" else 2
    golden_limit = 2 if plan == "pro" else 0

    # Trending deals (global)
    trending = (
        db.table("weekly_deals")
        .select("*")
        .is_("user_id", "null")
        .eq("deal_type", "global")
        .gte("valid_until", now_iso)
        .order("rank")
        .limit(trending_limit)
        .execute()
    )

    # Personal deals (for this user)
    personal = (
        db.table("weekly_deals")
        .select("*")
        .eq("user_id", user_id)
        .eq("deal_type", "personalised")
        .gte("valid_until", now_iso)
        .order("rank")
        .limit(personal_limit)
        .execute()
    )

    # Golden deals (PRO only)
    golden_data = []
    if golden_limit > 0:
        golden = (
            db.table("weekly_deals")
            .select("*")
            .eq("user_id", user_id)
            .eq("deal_type", "golden")
            .gte("valid_until", now_iso)
            .order("rank")
            .limit(golden_limit)
            .execute()
        )
        golden_data = golden.data or []

    # Seasonal deals (PRO only — Easter, Christmas, Halloween, etc)
    seasonal_data = []
    if plan == "pro":
        seasonal_data = _get_seasonal_deals(db, now)

    response = {
        "plan": plan,
        "trending": trending.data or [],
        "personalised": personal.data or [],
        "golden": golden_data,
        "seasonal": seasonal_data,
        "total": (
            len(trending.data or [])
            + len(personal.data or [])
            + len(golden_data)
            + len(seasonal_data)
        ),
        "refresh_days": 2 if plan == "pro" else 4,
    }

    set_cache(cache_key, response, ttl_seconds=3600)
    return response


def _get_seasonal_deals(db, now: datetime) -> list[dict]:
    """Find seasonal deals based on current date (Easter, Christmas, etc)."""
    month, day = now.month, now.day
    keywords = []
    season_name = None

    # Easter: March 15 - April 25
    if (month == 3 and day >= 15) or (month == 4 and day <= 25):
        keywords = ["easter", "egg", "chocolate egg", "hot cross", "lamb"]
        season_name = "Easter Specials"
    # Halloween: October 10 - November 2
    elif (month == 10 and day >= 10) or (month == 11 and day <= 2):
        keywords = ["halloween", "pumpkin", "trick", "sweets", "candy", "toffee"]
        season_name = "Halloween Treats"
    # Christmas: November 20 - December 31
    elif (month == 11 and day >= 20) or month == 12:
        keywords = ["christmas", "mince pie", "turkey", "stuffing", "cranberry", "prosecco", "champagne", "selection box"]
        season_name = "Christmas Deals"
    # Valentine's: February 7 - February 15
    elif month == 2 and 7 <= day <= 15:
        keywords = ["chocolate", "wine", "prosecco", "champagne", "heart"]
        season_name = "Valentine's Picks"
    # Summer BBQ: June - August
    elif month in (6, 7, 8):
        keywords = ["bbq", "burger", "sausage", "charcoal", "marinade", "coleslaw", "bun"]
        season_name = "BBQ Season"
    # Back to School: August 20 - September 15
    elif (month == 8 and day >= 20) or (month == 9 and day <= 15):
        keywords = ["lunch box", "snack bar", "juice box", "sandwich", "wrap"]
        season_name = "Back to School"

    if not keywords:
        return []

    now_iso = now.isoformat()
    seasonal = []
    seen = set()

    for kw in keywords[:5]:
        try:
            results = (
                db.table("collective_prices")
                .select("product_name, store_name, unit_price, category, is_on_offer")
                .eq("source", "leaflet")
                .gte("expires_at", now_iso)
                .ilike("product_name", f"%{kw}%")
                .order("unit_price")
                .limit(2)
                .execute()
            )
            for r in results.data or []:
                key = r["product_name"].lower()
                if key not in seen:
                    seen.add(key)
                    seasonal.append({
                        "product_name": r["product_name"],
                        "store_name": r["store_name"],
                        "current_price": float(r["unit_price"]),
                        "category": r.get("category", "Other"),
                        "deal_type": "seasonal",
                        "season": season_name,
                        "promotion_text": f"{season_name} — {r['product_name']} at €{r['unit_price']:.2f}",
                    })
        except Exception:
            continue

    return seasonal[:3]


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
