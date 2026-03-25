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
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=MANUAL_WINDOW_HOURS)

    # 1. Fetch recent alerts sent to this user
    alerts_resp = (
        db.table("alerts")
        .select("id, type, title, message, metadata, created_at")
        .eq("user_id", user_id)
        .gte("created_at", window_start.isoformat())
        .execute()
    )
    alerts = alerts_resp.data or []
    if not alerts:
        return []

    # 2. Fetch receipt items for this receipt
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

    # 3. Fetch receipt store
    receipt_resp = (
        db.table("receipts")
        .select("store_name, created_at")
        .eq("id", receipt_id)
        .single()
        .execute()
    )
    receipt_data = receipt_resp.data or {}
    receipt_store = (receipt_data.get("store_name") or "").lower()
    scanned_at = receipt_data.get("created_at") or now.isoformat()

    # Build a lookup of item names in the receipt (lowercased)
    item_lookup: dict[str, dict] = {}
    for it in items:
        name = (it.get("normalized_name") or "").lower().strip()
        if name:
            item_lookup[name] = it

    created: list[dict] = []

    for alert in alerts:
        meta = alert.get("metadata") or {}
        alert_product = (
            meta.get("product_name") or meta.get("product") or ""
        ).lower().strip()
        alert_store = (
            meta.get("store_name") or meta.get("store") or ""
        ).lower().strip()
        alert_price = meta.get("price") or meta.get("unit_price")
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

        # Calculate time difference
        try:
            from dateutil import parser as dateutil_parser

            alert_dt = dateutil_parser.isoparse(alerted_at)
            if alert_dt.tzinfo is None:
                alert_dt = alert_dt.replace(tzinfo=timezone.utc)
            hours_since = (now - alert_dt).total_seconds() / 3600
        except (ValueError, TypeError):
            hours_since = MANUAL_WINDOW_HOURS  # fallback

        # Determine attribution type
        if hours_since <= AUTO_WINDOW_HOURS:
            attribution_type = "automatic"
        elif hours_since <= MANUAL_WINDOW_HOURS:
            # Don't auto-attribute — eligible for manual confirmation
            continue
        else:
            continue

        # Calculate saving
        price_paid = matched_item.get("unit_price") or 0
        price_elsewhere = float(alert_price) if alert_price else 0
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
        .select("id, metadata, created_at")
        .eq("id", alert_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not alert_resp.data:
        return None

    alert = alert_resp.data
    meta = alert.get("metadata") or {}

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
    product_name = (
        meta.get("product_name") or meta.get("product") or "Unknown"
    )
    store = meta.get("store_name") or meta.get("store") or "Unknown"
    price_paid = meta.get("recommended_price") or meta.get("price") or 0
    price_elsewhere = meta.get("original_price") or meta.get("price_elsewhere") or 0
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
        .single()
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
