"""Payment endpoints for SmartDocket Pro subscriptions.

Uses RevenueCat for In-App Purchases (Apple/Google).
RevenueCat webhook syncs subscription status with Supabase.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.database import get_service_client

log = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/webhook/revenuecat")
async def revenuecat_webhook(request: Request):
    """Handle RevenueCat webhook events.

    RevenueCat sends events when subscriptions are created, renewed,
    cancelled, etc. We use these to sync Pro status with Supabase.
    """
    auth_header = request.headers.get("Authorization", "")
    expected = f"Bearer {settings.REVENUECAT_WEBHOOK_SECRET}" if hasattr(settings, 'REVENUECAT_WEBHOOK_SECRET') and settings.REVENUECAT_WEBHOOK_SECRET else ""
    if not expected or auth_header != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook auth")

    body = await request.json()
    event = body.get("event", {})
    event_type = event.get("type", "")
    app_user_id = event.get("app_user_id", "")

    if not app_user_id:
        log.warning("RevenueCat webhook: no app_user_id")
        return {"status": "ignored"}

    db = get_service_client()

    ACTIVE_EVENTS = {
        "INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION",
        "NON_RENEWING_PURCHASE", "SUBSCRIPTION_EXTENDED", "PRODUCT_CHANGE",
    }
    INACTIVE_EVENTS = {
        "EXPIRATION", "BILLING_ISSUE", "SUBSCRIPTION_PAUSED",
    }

    if event_type in ACTIVE_EVENTS:
        expiration = event.get("expiration_at_ms")
        if expiration:
            expires_at = datetime.fromtimestamp(expiration / 1000, tz=timezone.utc)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(days=35)

        db.table("profiles").update({
            "plan": "pro",
            "plan_expires_at": expires_at.isoformat(),
        }).eq("id", app_user_id).execute()

        log.info("RevenueCat: %s → Pro (event: %s)", app_user_id, event_type)

        if event_type == "INITIAL_PURCHASE":
            try:
                user_q = db.table("profiles").select("email").eq("id", app_user_id).maybe_single().execute()
                email = (user_q.data or {}).get("email")
                if email:
                    await _send_pro_welcome_email(email, expires_at)
            except Exception as e:
                log.warning("RevenueCat: welcome email failed: %s", e)

        _award_deferred_referral(db, app_user_id)

    elif event_type in INACTIVE_EVENTS:
        db.table("profiles").update({
            "plan": "free",
            "plan_expires_at": None,
        }).eq("id", app_user_id).execute()
        log.info("RevenueCat: %s → Free (event: %s)", app_user_id, event_type)

    elif event_type == "CANCELLATION":
        log.info("RevenueCat: %s cancelled (access until expiry)", app_user_id)

    return {"status": "ok"}


# --- Legacy Stripe webhook for existing subscribers ---

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events (legacy)."""
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
    except Exception:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")

    db = get_service_client()

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session.get("customer_email", "")
        expires = datetime.now(timezone.utc) + timedelta(days=365)
        if email:
            db.table("profiles").update({
                "plan": "pro",
                "plan_expires_at": expires.isoformat(),
            }).eq("email", email).execute()
            log.info("Stripe: %s → Pro", email)

    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        try:
            customer = stripe.Customer.retrieve(sub.get("customer", ""))
            email = customer.get("email", "")
            if email:
                db.table("profiles").update({
                    "plan": "free", "plan_expires_at": None,
                }).eq("email", email).execute()
        except Exception as e:
            log.error("Stripe cancellation error: %s", e)

    return {"status": "ok"}


def _award_deferred_referral(db, user_id: str):
    """Award referral points when user upgrades to Pro."""
    try:
        profile = db.table("profiles").select("referred_by").eq("id", user_id).maybe_single().execute()
        referred_by = (profile.data or {}).get("referred_by")
        if not referred_by:
            return
        referrer = db.table("profiles").select("id, points, plan").eq("referral_code", referred_by).maybe_single().execute()
        if not referrer.data:
            return
        current_pts = referrer.data.get("points") or 0
        award = 25 if referrer.data.get("plan") == "pro" else 50
        db.table("profiles").update({"points": current_pts + award}).eq("id", referrer.data["id"]).execute()
        log.info("Referral: +%d pts to %s", award, referrer.data["id"])
    except Exception as e:
        log.warning("Referral check failed: %s", e)


async def _send_pro_welcome_email(email: str, expires: datetime):
    """Send welcome email on Pro upgrade."""
    from app.services.email_service import send_email
    html = f"""
    <div style="font-family:'Segoe UI',Helvetica,Arial,sans-serif;max-width:500px;margin:0 auto;
                background:#0d2818;color:#e8f5ec;padding:32px;border-radius:12px">
      <div style="text-align:center;margin-bottom:24px"><span style="font-size:48px">👑</span></div>
      <h1 style="text-align:center;color:#7DDFAA;margin:0 0 8px;font-size:24px">Welcome to SmartDocket Pro!</h1>
      <p style="text-align:center;color:#a0c4ab;margin:0 0 24px;font-size:14px">Your upgrade is confirmed</p>
      <div style="background:rgba(255,255,255,0.06);border-radius:8px;padding:20px;margin-bottom:20px">
        <p style="margin:0 0 12px;font-size:15px"><strong style="color:#7DDFAA">✓ Unlimited receipt scans</strong></p>
        <p style="margin:0 0 12px;font-size:15px"><strong style="color:#7DDFAA">✓ Unlimited AI chat queries</strong></p>
        <p style="margin:0 0 12px;font-size:15px"><strong style="color:#7DDFAA">✓ Priority price alerts</strong></p>
        <p style="margin:0;font-size:15px"><strong style="color:#7DDFAA">✓ Advanced spending insights</strong></p>
      </div>
      <p style="font-size:13px;color:#a0c4ab;text-align:center">
        Active until <strong style="color:#e8f5ec">{expires.strftime("%B %d, %Y")}</strong></p>
      <p style="font-size:12px;color:#6a8a72;text-align:center;margin-top:20px">Thank you! 💚</p>
    </div>
    """
    await send_email(email, "👑 Welcome to SmartDocket Pro!", html)
