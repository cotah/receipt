import math
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from app.utils.auth_utils import get_current_user
from app.utils.text_utils import generate_product_key
from app.database import get_service_client
from app.models.product import (
    ProductHistory,
    PricePoint,
    PriceExtreme,
    CategoriesResponse,
    CategorySummary,
    RunningLowResponse,
    RunningLowItem,
    BestPrice,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/history", response_model=ProductHistory)
async def get_product_history(
    name: str = Query(...),
    months: int = Query(6),
    user_id: str = Depends(get_current_user),
):
    db = get_service_client()
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=months * 30)).isoformat()

    items = (
        db.table("receipt_items")
        .select("*, receipts(purchased_at, store_name)")
        .eq("user_id", user_id)
        .eq("normalized_name", name)
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .execute()
    )
    data = items.data or []

    prices = [d["unit_price"] for d in data]
    avg_price = sum(prices) / len(prices) if prices else 0

    price_history = []
    dates = []
    for d in data:
        receipt = d.get("receipts") or {}
        p_date = receipt.get("purchased_at", d["created_at"])
        dates.append(datetime.fromisoformat(p_date))
        price_history.append(PricePoint(
            date=p_date[:10],
            store=receipt.get("store_name", "Unknown"),
            price=d["unit_price"],
            unit=d.get("unit"),
        ))

    # Calculate average days between purchases
    avg_days = None
    if len(dates) >= 2:
        sorted_dates = sorted(dates)
        intervals = [(sorted_dates[i + 1] - sorted_dates[i]).days for i in range(len(sorted_dates) - 1)]
        avg_days = sum(intervals) / len(intervals) if intervals else None

    predicted_next = None
    if avg_days and dates:
        last = max(dates)
        predicted_next = (last + timedelta(days=avg_days)).date()

    cheapest = None
    most_expensive = None
    if data:
        cheapest_item = min(data, key=lambda x: x["unit_price"])
        receipt_c = cheapest_item.get("receipts") or {}
        cheapest = PriceExtreme(
            price=cheapest_item["unit_price"],
            store=receipt_c.get("store_name", "Unknown"),
            date=(receipt_c.get("purchased_at", cheapest_item["created_at"]))[:10],
        )
        expensive_item = max(data, key=lambda x: x["unit_price"])
        receipt_e = expensive_item.get("receipts") or {}
        most_expensive = PriceExtreme(
            price=expensive_item["unit_price"],
            store=receipt_e.get("store_name", "Unknown"),
            date=(receipt_e.get("purchased_at", expensive_item["created_at"]))[:10],
        )

    category = data[0]["category"] if data else "Other"

    return ProductHistory(
        product_name=name,
        category=category,
        purchase_count=len(data),
        avg_days_between_purchases=round(avg_days, 1) if avg_days else None,
        predicted_next_purchase=predicted_next,
        price_history=price_history,
        avg_price=round(avg_price, 2),
        cheapest_ever=cheapest,
        most_expensive_ever=most_expensive,
    )


@router.get("/categories", response_model=CategoriesResponse)
async def get_categories(
    period: str = Query("month"),
    user_id: str = Depends(get_current_user),
):
    db = get_service_client()
    now = datetime.now(timezone.utc)

    if period == "week":
        start = (now - timedelta(days=7)).isoformat()
        prev_start = (now - timedelta(days=14)).isoformat()
        prev_end = (now - timedelta(days=7)).isoformat()
        period_label = "This Week"
    elif period == "year":
        start = datetime(now.year, 1, 1, tzinfo=timezone.utc).isoformat()
        prev_start = datetime(now.year - 1, 1, 1, tzinfo=timezone.utc).isoformat()
        prev_end = datetime(now.year, 1, 1, tzinfo=timezone.utc).isoformat()
        period_label = str(now.year)
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        prev_month = now.replace(day=1) - timedelta(days=1)
        prev_start = prev_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        prev_end = start
        period_label = now.strftime("%Y-%m")

    # Current period items
    items = (
        db.table("receipt_items")
        .select("category, total_price")
        .eq("user_id", user_id)
        .gte("created_at", start)
        .execute()
    )

    # Previous period items
    prev_items = (
        db.table("receipt_items")
        .select("category, total_price")
        .eq("user_id", user_id)
        .gte("created_at", prev_start)
        .lt("created_at", prev_end)
        .execute()
    )

    # Aggregate current
    cat_map: dict[str, dict] = {}
    total_all = 0.0
    for item in items.data or []:
        cat = item["category"]
        if cat not in cat_map:
            cat_map[cat] = {"total": 0.0, "count": 0}
        cat_map[cat]["total"] += item["total_price"]
        cat_map[cat]["count"] += 1
        total_all += item["total_price"]

    # Aggregate previous
    prev_map: dict[str, float] = {}
    for item in prev_items.data or []:
        cat = item["category"]
        prev_map[cat] = prev_map.get(cat, 0) + item["total_price"]

    categories = []
    for cat, data in cat_map.items():
        prev_total = prev_map.get(cat, 0)
        trend_pct = ((data["total"] - prev_total) / prev_total * 100) if prev_total > 0 else 0
        categories.append(CategorySummary(
            name=cat,
            total_spent=round(data["total"], 2),
            percentage=round(data["total"] / total_all * 100, 1) if total_all > 0 else 0,
            items_count=data["count"],
            trend="up" if trend_pct > 0 else "down" if trend_pct < 0 else "stable",
            trend_percent=round(abs(trend_pct), 1),
        ))
    categories.sort(key=lambda x: -x.total_spent)

    return CategoriesResponse(period=period_label, categories=categories)


@router.get("/running-low", response_model=RunningLowResponse)
async def get_running_low(user_id: str = Depends(get_current_user)):
    db = get_service_client()
    now = datetime.now(timezone.utc)

    try:
        patterns = (
            db.table("user_product_patterns")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
    except Exception:
        return RunningLowResponse(items=[])

    items = []
    for p in patterns.data or []:
        avg_days = p.get("avg_days_between_purchases")
        if avg_days is None or avg_days <= 0:
            continue
        if p.get("purchase_count", 0) < 3:
            continue

        last = datetime.fromisoformat(p["last_purchased_at"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        days_since = (now - last).days

        if days_since < avg_days:
            continue

        overdue = int(days_since - avg_days)
        if overdue <= 0:
            urgency = "low"
        elif overdue <= avg_days * 0.5:
            urgency = "medium"
        else:
            urgency = "high"

        # Best current price
        product_key = generate_product_key(p["normalized_name"])
        best_resp = (
            db.table("collective_prices")
            .select("store_name, unit_price")
            .eq("product_key", product_key)
            .gte("expires_at", now.isoformat())
            .order("unit_price")
            .limit(1)
            .execute()
        )
        best = None
        if best_resp.data:
            best = BestPrice(store=best_resp.data[0]["store_name"], price=best_resp.data[0]["unit_price"])

        items.append(RunningLowItem(
            product_name=p["normalized_name"],
            last_purchased=last,
            avg_days_cycle=round(avg_days, 1),
            days_since_last=days_since,
            overdue_by_days=overdue,
            urgency=urgency,
            typical_store=None,
            typical_price=p.get("avg_price"),
            best_current_price=best,
        ))

    items.sort(key=lambda x: -x.overdue_by_days)
    return RunningLowResponse(items=items)
