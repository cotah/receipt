"""Push notification service — sends Expo push notifications."""

import logging
from typing import Optional

import httpx

log = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


async def send_push_notification(
    push_token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> bool:
    """Send a push notification via Expo Push API.

    Args:
        push_token: Expo push token (ExponentPushToken[xxx])
        title: Notification title
        body: Notification body text
        data: Optional data payload (for navigation etc)

    Returns:
        True if sent successfully, False otherwise
    """
    if not push_token or not push_token.startswith("ExponentPushToken"):
        log.debug("Invalid push token: %s", push_token[:20] if push_token else "None")
        return False

    payload = {
        "to": push_token,
        "title": title,
        "body": body,
        "sound": "default",
        "priority": "high",
    }
    if data:
        payload["data"] = data

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                EXPO_PUSH_URL,
                json=payload,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code == 200:
                result = resp.json()
                ticket = result.get("data", {})
                if ticket.get("status") == "ok":
                    log.info("Push sent to %s...%s", push_token[:25], push_token[-5:])
                    return True
                else:
                    log.warning("Push ticket error: %s", ticket)
                    return False
            else:
                log.warning("Push API error: %d %s", resp.status_code, resp.text[:200])
                return False
    except Exception as e:
        log.warning("Push notification failed: %s", e)
        return False


async def send_golden_deal_alerts(db, golden_deals: list[dict], user_id: str) -> int:
    """Send push notification for new Golden Deals to a PRO user.

    Args:
        db: Supabase client
        golden_deals: List of golden deal dicts
        user_id: User ID

    Returns:
        Number of notifications sent
    """
    if not golden_deals:
        return 0

    try:
        profile = (
            db.table("profiles")
            .select("push_token, full_name")
            .eq("id", user_id)
            .single()
            .execute()
        )
        token = (profile.data or {}).get("push_token")
        name = (profile.data or {}).get("full_name", "").split(" ")[0] or "Hey"

        if not token:
            return 0

        # Build notification
        best = max(golden_deals, key=lambda d: d.get("discount_pct", 0))
        count = len(golden_deals)

        if count == 1:
            title = "🥇 Golden Deal Found!"
            body = (
                f"{best['product_name']} is {best.get('discount_pct', 0)}% "
                f"below average at {best['store_name']} — €{best['current_price']:.2f}"
            )
        else:
            title = f"🥇 {count} Golden Deals for you!"
            body = (
                f"{name}, {best['product_name']} and {count - 1} more "
                f"products are at exceptional prices right now"
            )

        sent = await send_push_notification(
            push_token=token,
            title=title,
            body=body,
            data={"screen": "offers", "deal_type": "golden"},
        )
        return 1 if sent else 0

    except Exception as e:
        log.warning("Golden deal alert failed for %s: %s", user_id[:8], e)
        return 0
