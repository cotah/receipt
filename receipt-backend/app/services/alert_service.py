from datetime import datetime, timedelta, timezone
from supabase import Client
from app.services.price_service import get_best_price
from app.utils.text_utils import generate_product_key

RESTOCK_THRESHOLD_MULTIPLIER = 1.5


async def generate_restock_alerts(db: Client, user_id: str) -> None:
    """Check products that the user buys cyclically and alert when overdue."""
    now = datetime.now(timezone.utc)

    try:
        patterns = (
            db.table("user_product_patterns")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
    except Exception:
        return

    for pattern in patterns.data or []:
        avg_days = pattern.get("avg_days_between_purchases")
        if avg_days is None or avg_days <= 0:
            continue
        if pattern.get("purchase_count", 0) < 3:
            continue

        last_purchased = datetime.fromisoformat(pattern["last_purchased_at"])
        if last_purchased.tzinfo is None:
            last_purchased = last_purchased.replace(tzinfo=timezone.utc)

        days_since = (now - last_purchased).days
        threshold = avg_days * RESTOCK_THRESHOLD_MULTIPLIER

        if days_since < threshold:
            continue

        # Check if we already sent this alert recently
        existing = (
            db.table("alerts")
            .select("id, created_at")
            .eq("user_id", user_id)
            .eq("type", "restock")
            .eq("product_name", pattern["normalized_name"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if existing.data:
            alert_age = (now - datetime.fromisoformat(existing.data[0]["created_at"]).replace(tzinfo=timezone.utc)).days
            if alert_age < 2:
                continue

        # Get best current price
        product_key = generate_product_key(pattern["normalized_name"])
        best_price = await get_best_price(db, product_key)

        overdue_days = int(days_since - avg_days)
        message = build_restock_message(pattern, best_price, days_since)

        db.table("alerts").insert(
            {
                "user_id": user_id,
                "type": "restock",
                "product_name": pattern["normalized_name"],
                "message": message,
                "data": {
                    "days_overdue": overdue_days,
                    "avg_cycle": avg_days,
                    "best_store": best_price["store_name"] if best_price else None,
                    "best_price": float(best_price["unit_price"]) if best_price else None,
                },
            }
        ).execute()


async def generate_price_drop_alerts(db: Client, user_id: str) -> None:
    """Detect price drops for products the user regularly buys. Pro only — sends push."""
    from app.utils.plan_utils import is_pro
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=60)).isoformat()

    # Check if user is Pro (price drop alerts are Pro-only)
    try:
        profile = (
            db.table("profiles")
            .select("plan, plan_expires_at, push_token")
            .eq("id", user_id)
            .single()
            .execute()
        )
        if not is_pro(profile.data or {}):
            return  # Free users don't get price drop alerts
        push_token = (profile.data or {}).get("push_token")
    except Exception:
        return

    # Products bought in last 60 days with avg price
    try:
        recent = (
            db.table("user_product_patterns")
            .select("normalized_name, avg_price, category")
            .eq("user_id", user_id)
            .gte("last_purchased_at", cutoff)
            .execute()
        )
    except Exception:
        return

    for product in recent.data or []:
        product_key = generate_product_key(product["normalized_name"])
        best = await get_best_price(db, product_key)
        if not best:
            continue

        avg_price = product["avg_price"]
        if avg_price <= 0:
            continue

        # Alert if collective price is >15% cheaper
        if best["unit_price"] < avg_price * 0.85:
            saving = avg_price - best["unit_price"]

            # Check if already alerted recently
            existing = (
                db.table("alerts")
                .select("id")
                .eq("user_id", user_id)
                .eq("type", "price_drop")
                .eq("product_name", product["normalized_name"])
                .gte("created_at", (now - timedelta(days=3)).isoformat())
                .limit(1)
                .execute()
            )
            if existing.data:
                continue

            message = (
                f"{product['normalized_name']} is €{best['unit_price']:.2f} "
                f"at {best['store_name']} — you usually pay €{avg_price:.2f}. "
                f"Save €{saving:.2f}!"
            )

            db.table("alerts").insert(
                {
                    "user_id": user_id,
                    "type": "price_drop",
                    "product_name": product["normalized_name"],
                    "store_name": best["store_name"],
                    "message": message,
                    "data": {
                        "current_price": float(best["unit_price"]),
                        "usual_price": float(avg_price),
                        "saving": float(saving),
                        "store": best["store_name"],
                    },
                }
            ).execute()

            # Send push notification (Pro only)
            if push_token:
                from app.services.push_service import send_push_notification
                await send_push_notification(
                    push_token=push_token,
                    title="📉 Price Drop!",
                    body=f"{product['normalized_name']} down to €{best['unit_price']:.2f} at {best['store_name']} — save €{saving:.2f}",
                    data={"screen": "alerts", "type": "price_drop"},
                )


def build_restock_message(pattern: dict, best_price: dict | None, days_since: float) -> str:
    avg_days = pattern["avg_days_between_purchases"]
    name = pattern["normalized_name"]
    msg = f"You usually buy {name} every {avg_days:.0f} days — it's been {int(days_since)} days."
    if best_price:
        msg += f" {best_price['store_name']} has them for €{best_price['unit_price']:.2f} right now."
    return msg
