"""Savings attribution — links SmartDocket alerts to actual purchases."""

import logging
from datetime import datetime, timedelta, timezone

from supabase import Client

log = logging.getLogger(__name__)

# Window thresholds (hours after alert was sent)
AUTO_WINDOW_HOURS = 5    # automatic attribution
MANUAL_WINDOW_HOURS = 8  # eligible for manual confirmation


async def check_attribution(
    db: Client,
    user_id: str,
    receipt_id: str,
) -> list[dict]:
    """Check if any recent alerts match items in this receipt.

    Called after a successful scan.  Returns a list of created
    attribution records (may be empty).

    IMPORTANT: Uses the receipt's purchased_at time (printed on receipt),
    NOT the upload time. This way if someone bought at 16:00 after an
    alert at 14:00, but uploaded the receipt 2 days later, we still
    correctly attribute the saving (16:00 - 14:00 = 2h < 5h window).
    """
    now = datetime.now(timezone.utc)

    # 1. Get the receipt's actual purchase time
    receipt_resp = (
        db.table("receipts")
        .select("store_name, purchased_at, created_at")
        .eq("id", receipt_id)
        .maybe_single()
        .execute()
    )
    receipt_data = receipt_resp.data or {}
    receipt_store = (receipt_data.get("store_name") or "").lower()
    scanned_at = receipt_data.get("created_at") or now.isoformat()

    # Use purchased_at (time on receipt) for attribution, not upload time
    purchase_time = now
    try:
        from dateutil import parser as dateutil_parser
        raw_purchased = receipt_data.get("purchased_at")
        if raw_purchased:
            purchase_time = dateutil_parser.isoparse(raw_purchased)
            if purchase_time.tzinfo is None:
                purchase_time = purchase_time.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        pass  # fallback to now

    # Look for alerts in a wider window around the PURCHASE time
    # (not around upload time)
    window_start = purchase_time - timedelta(hours=MANUAL_WINDOW_HOURS)

    # 2. Fetch alerts sent to this user around the purchase time
    alerts_resp = (
        db.table("alerts")
        .select("id, type, product_name, store_name, message, data, created_at")
        .eq("user_id", user_id)
        .gte("created_at", window_start.isoformat())
        .lte("created_at", purchase_time.isoformat())
        .execute()
    )
    alerts = alerts_resp.data or []
    if not alerts:
        return []

    # 3. Fetch receipt items
    items_resp = (
        db.table("receipt_items")
        .select(
            "normalized_name, unit_price, total_price, quantity"
        )
        .eq("receipt_id", receipt_id)
        .execute()
    )
    items = items_resp.data or []
    if not items:
        return []

    # Build a lookup of item names in the receipt (lowercased)
    item_lookup: dict[str, dict] = {}
    for it in items:
        name = (it.get("normalized_name") or "").lower().strip()
        if name:
            item_lookup[name] = it

    created: list[dict] = []

    for alert in alerts:
        alert_data = alert.get("data") or {}
        alert_product = (
            alert.get("product_name") or ""
        ).lower().strip()
        alert_store = (
            alert.get("store_name") or alert_data.get("store") or ""
        ).lower().strip()
        usual_price = alert_data.get("usual_price") or alert_data.get("price_elsewhere") or 0
        alerted_at = alert["created_at"]

        if not alert_product:
            continue

        # Check if product is in receipt (fuzzy: one contains the other)
        matched_item = None
        for item_name, item_data in item_lookup.items():
            if alert_product in item_name or item_name in alert_product:
                matched_item = item_data
                break

        if matched_item is None:
            continue

        # Check store match (receipt store contains alert store or vice versa)
        if alert_store and receipt_store:
            if (
                alert_store not in receipt_store
                and receipt_store not in alert_store
            ):
                continue

        # Calculate time between ALERT and PURCHASE (not upload)
        try:
            alert_dt = dateutil_parser.isoparse(alerted_at)
            if alert_dt.tzinfo is None:
                alert_dt = alert_dt.replace(tzinfo=timezone.utc)
            hours_since = (purchase_time - alert_dt).total_seconds() / 3600
        except (ValueError, TypeError):
            hours_since = MANUAL_WINDOW_HOURS  # fallback

        # Only count if alert was BEFORE purchase (not after)
        if hours_since < 0:
            continue

        # Determine attribution type
        if hours_since <= AUTO_WINDOW_HOURS:
            attribution_type = "automatic"
        elif hours_since <= MANUAL_WINDOW_HOURS:
            # Don't auto-attribute — eligible for manual confirmation
            continue
        else:
            continue

        # Calculate saving
        # price_paid = what the user paid on the receipt (the deal price)
        # price_elsewhere = what they usually pay (from alert's usual_price)
        price_paid = float(matched_item.get("unit_price") or 0)
        price_elsewhere = float(usual_price) if usual_price else 0
        saving = max(price_elsewhere - price_paid, 0)

        if saving <= 0:
            continue

        # Create attribution record
        record = {
            "user_id": user_id,
            "alert_id": alert["id"],
            "receipt_id": receipt_id,
            "product_name": matched_item.get("normalized_name", ""),
            "store": receipt_data.get("store_name", ""),
            "price_paid": price_paid,
            "price_elsewhere": price_elsewhere,
            "saving": round(saving, 2),
            "attribution": attribution_type,
            "alerted_at": alerted_at,
            "scanned_at": scanned_at,
        }
        try:
            db.table("savings_attributions").insert(record).execute()
            created.append(record)
            log.info(
                "Attribution: %s saved €%.2f on %s at %s (auto)",
                user_id[:8],
                saving,
                record["product_name"],
                record["store"],
            )
        except Exception as e:
            log.warning("Attribution insert failed: %s", e)

    return created


async def confirm_saving(
    db: Client,
    user_id: str,
    alert_id: str,
) -> dict | None:
    """Manually confirm a saving from an alert (5-8h window).

    Returns the attribution record or None if not eligible.
    """
    now = datetime.now(timezone.utc)

    # Fetch the alert
    alert_resp = (
        db.table("alerts")
        .select("id, product_name, store_name, data, created_at")
        .eq("id", alert_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not alert_resp.data:
        return None

    alert = alert_resp.data
    alert_data = alert.get("data") or {}

    # Check time window
    from dateutil import parser as dateutil_parser

    try:
        alert_dt = dateutil_parser.isoparse(alert["created_at"])
        if alert_dt.tzinfo is None:
            alert_dt = alert_dt.replace(tzinfo=timezone.utc)
        hours_since = (now - alert_dt).total_seconds() / 3600
    except (ValueError, TypeError):
        return None

    if hours_since > MANUAL_WINDOW_HOURS:
        return None  # Too old

    # Check not already attributed
    existing = (
        db.table("savings_attributions")
        .select("id")
        .eq("alert_id", alert_id)
        .eq("user_id", user_id)
        .execute()
    )
    if existing.data:
        return None  # Already attributed

    # Build record
    product_name = alert.get("product_name") or "Unknown"
    store = alert.get("store_name") or alert_data.get("store") or "Unknown"
    price_paid = alert_data.get("current_price") or 0
    price_elsewhere = alert_data.get("usual_price") or 0
    saving = max(float(price_elsewhere) - float(price_paid), 0)

    record = {
        "user_id": user_id,
        "alert_id": alert_id,
        "product_name": product_name,
        "store": store,
        "price_paid": float(price_paid),
        "price_elsewhere": float(price_elsewhere),
        "saving": round(saving, 2),
        "attribution": "confirmed",
        "alerted_at": alert["created_at"],
        "scanned_at": now.isoformat(),
    }

    db.table("savings_attributions").insert(record).execute()

    # Award 10 bonus points
    profile = (
        db.table("profiles")
        .select("points")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    current_pts = (profile.data or {}).get("points") or 0
    db.table("profiles").update(
        {"points": current_pts + 10}
    ).eq("id", user_id).execute()

    return {
        "saving": record["saving"],
        "product": product_name,
        "store": store,
        "points_earned": 10,
    }


def get_total_smartdocket_savings(db: Client, user_id: str) -> float:
    """Sum of all attributed savings for a user."""
    resp = (
        db.table("savings_attributions")
        .select("saving")
        .eq("user_id", user_id)
        .execute()
    )
    return round(sum(r["saving"] for r in (resp.data or [])), 2)


def get_monthly_smartdocket_savings(
    db: Client,
    user_id: str,
    month_start: str,
    month_end: str,
) -> float:
    """Sum of attributed savings for a user in a specific month."""
    resp = (
        db.table("savings_attributions")
        .select("saving")
        .eq("user_id", user_id)
        .gte("created_at", month_start)
        .lte("created_at", month_end)
        .execute()
    )
    return round(sum(r["saving"] for r in (resp.data or [])), 2)
