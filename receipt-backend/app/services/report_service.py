from datetime import datetime, timezone
from calendar import monthrange
from supabase import Client


async def generate_monthly_report(db: Client, user_id: str, month: str) -> dict:
    """Generate full monthly report. month format: '2026-03'."""
    year, mon = map(int, month.split("-"))
    start = datetime(year, mon, 1, tzinfo=timezone.utc)
    _, last_day = monthrange(year, mon)
    end = datetime(year, mon, last_day, 23, 59, 59, tzinfo=timezone.utc)

    # Previous month
    if mon == 1:
        prev_start = datetime(year - 1, 12, 1, tzinfo=timezone.utc)
        _, prev_last = monthrange(year - 1, 12)
        prev_end = datetime(year - 1, 12, prev_last, 23, 59, 59, tzinfo=timezone.utc)
    else:
        prev_start = datetime(year, mon - 1, 1, tzinfo=timezone.utc)
        _, prev_last = monthrange(year, mon - 1)
        prev_end = datetime(year, mon - 1, prev_last, 23, 59, 59, tzinfo=timezone.utc)

    # Current month receipts
    receipts = (
        db.table("receipts")
        .select("id, store_name, total_amount, discount_total, purchased_at")
        .eq("user_id", user_id)
        .gte("purchased_at", start.isoformat())
        .lte("purchased_at", end.isoformat())
        .eq("status", "done")
        .execute()
    )
    receipt_data = receipts.data or []

    # Previous month receipts
    prev_receipts = (
        db.table("receipts")
        .select("total_amount")
        .eq("user_id", user_id)
        .gte("purchased_at", prev_start.isoformat())
        .lte("purchased_at", prev_end.isoformat())
        .eq("status", "done")
        .execute()
    )
    prev_total = sum(r["total_amount"] for r in (prev_receipts.data or []))

    # Summary
    total_spent = sum(r["total_amount"] for r in receipt_data)
    total_saved = sum(r.get("discount_total", 0) for r in receipt_data)
    receipts_count = len(receipt_data)
    avg_basket = total_spent / receipts_count if receipts_count > 0 else 0

    diff = total_spent - prev_total
    diff_pct = (diff / prev_total * 100) if prev_total > 0 else 0
    trend = "down" if diff < 0 else "up" if diff > 0 else "stable"

    # Items
    receipt_ids = [r["id"] for r in receipt_data]
    items_data = []
    if receipt_ids:
        items_resp = (
            db.table("receipt_items")
            .select("normalized_name, category, total_price, unit_price, is_on_offer")
            .eq("user_id", user_id)
            .in_("receipt_id", receipt_ids)
            .execute()
        )
        items_data = items_resp.data or []

    items_count = len(items_data)

    # By store
    store_map: dict[str, dict] = {}
    for r in receipt_data:
        s = r["store_name"]
        if s not in store_map:
            store_map[s] = {"store": s, "total": 0.0, "visits": 0, "percentage": 0}
        store_map[s]["total"] += r["total_amount"]
        store_map[s]["visits"] += 1
    by_store = list(store_map.values())
    for s in by_store:
        s["percentage"] = round(s["total"] / total_spent * 100, 1) if total_spent > 0 else 0
        s["total"] = round(s["total"], 2)
    by_store.sort(key=lambda x: -x["total"])

    # By category
    cat_map: dict[str, dict] = {}
    for item in items_data:
        cat = item["category"]
        if cat not in cat_map:
            cat_map[cat] = {"category": cat, "total": 0.0, "items_count": 0, "top_items": {}}
        cat_map[cat]["total"] += item["total_price"]
        cat_map[cat]["items_count"] += 1
        name = item["normalized_name"]
        cat_map[cat]["top_items"][name] = cat_map[cat]["top_items"].get(name, 0) + item["total_price"]

    by_category = []
    for cat, data in cat_map.items():
        top = sorted(data["top_items"].items(), key=lambda x: -x[1])[:3]
        by_category.append({
            "category": cat,
            "total": round(data["total"], 2),
            "percentage": round(data["total"] / total_spent * 100, 1) if total_spent > 0 else 0,
            "top_items": [name for name, _ in top],
        })
    by_category.sort(key=lambda x: -x["total"])

    # Insights
    insights = generate_insights(total_spent, prev_total, diff_pct, by_store, by_category)

    # Price wins
    price_wins = []
    seen = set()
    for item in items_data:
        name = item["normalized_name"]
        if name in seen:
            continue
        seen.add(name)
        # Check collective average
        collective = (
            db.table("collective_prices")
            .select("unit_price, store_name")
            .eq("product_name", name)
            .execute()
        )
        if collective.data and len(collective.data) >= 2:
            avg_market = sum(p["unit_price"] for p in collective.data) / len(collective.data)
            if item["unit_price"] < avg_market * 0.9:
                price_wins.append({
                    "product": name,
                    "store": next(
                        (r["store_name"] for r in receipt_data),
                        "Unknown",
                    ),
                    "price": item["unit_price"],
                    "avg_market_price": round(avg_market, 2),
                    "saved": round(avg_market - item["unit_price"], 2),
                })
        if len(price_wins) >= 5:
            break

    # Discounts by store
    discount_store_map: dict[str, dict] = {}
    for r in receipt_data:
        s = r["store_name"]
        disc = r.get("discount_total", 0) or 0
        if disc <= 0:
            continue
        if s not in discount_store_map:
            discount_store_map[s] = {
                "store": s,
                "total_discount": 0.0,
                "offers_count": 0,
            }
        discount_store_map[s]["total_discount"] += disc
        discount_store_map[s]["offers_count"] += 1
    discounts_by_store = sorted(
        discount_store_map.values(),
        key=lambda x: -x["total_discount"],
    )
    for d in discounts_by_store:
        d["total_discount"] = round(d["total_discount"], 2)

    # Previous month saved
    prev_saved = sum(
        r.get("discount_total", 0) for r in (prev_receipts.data or [])
    )

    period_label = start.strftime("%B %Y")
    prev_period_label = prev_start.strftime("%B %Y")
    return {
        "period": period_label,
        "summary": {
            "total_spent": round(total_spent, 2),
            "total_saved": round(total_saved, 2),
            "prev_saved": round(prev_saved, 2),
            "receipts_count": receipts_count,
            "items_count": items_count,
            "avg_basket_size": round(avg_basket, 2),
            "vs_previous_month": {
                "amount": round(diff, 2),
                "percent": round(diff_pct, 1),
                "trend": trend,
                "previous_total": round(prev_total, 2),
                "previous_period": prev_period_label,
            },
        },
        "by_store": by_store,
        "by_category": by_category,
        "discounts_by_store": discounts_by_store,
        "insights": insights,
        "price_wins": price_wins,
    }


def generate_insights(
    total: float, prev_total: float, diff_pct: float,
    by_store: list, by_category: list
) -> list[str]:
    insights = []
    if diff_pct < 0:
        insights.append(f"You spent {abs(diff_pct):.0f}% less than last month. Well done!")
    elif diff_pct > 10:
        insights.append(f"Spending is up {diff_pct:.0f}% compared to last month.")

    if by_store:
        cheapest = by_store[-1] if len(by_store) > 1 else by_store[0]
        insights.append(f"{cheapest['store']} had your lowest average basket this month.")

    if by_category:
        top_cat = by_category[0]
        insights.append(
            f"{top_cat['category']} was your biggest category at €{top_cat['total']:.2f} "
            f"({top_cat['percentage']}% of spending)."
        )

    if not insights:
        insights.append("Keep scanning receipts to unlock more insights!")

    return insights[:5]


async def generate_yearly_overview(db: Client, user_id: str) -> dict:
    """Aggregate monthly totals for the current year."""
    now = datetime.now(timezone.utc)
    year_start = datetime(now.year, 1, 1, tzinfo=timezone.utc)

    receipts = (
        db.table("receipts")
        .select("total_amount, discount_total, purchased_at")
        .eq("user_id", user_id)
        .gte("purchased_at", year_start.isoformat())
        .eq("status", "done")
        .execute()
    )

    monthly: dict[str, dict] = {}
    for r in receipts.data or []:
        month_key = r["purchased_at"][:7]  # "2026-03"
        if month_key not in monthly:
            monthly[month_key] = {"month": month_key, "total": 0.0, "saved": 0.0, "receipts": 0}
        monthly[month_key]["total"] += r["total_amount"]
        monthly[month_key]["saved"] += r.get("discount_total", 0)
        monthly[month_key]["receipts"] += 1

    months = sorted(monthly.values(), key=lambda x: x["month"])
    return {
        "year": now.year,
        "months": months,
        "year_total": round(sum(m["total"] for m in months), 2),
        "year_saved": round(sum(m["saved"] for m in months), 2),
    }
