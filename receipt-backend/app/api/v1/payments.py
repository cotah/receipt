"""Stripe payment endpoints for SmartDocket Pro subscriptions."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import settings
from app.database import get_service_client

log = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])

stripe.api_key = settings.STRIPE_SECRET_KEY


class CheckoutRequest(BaseModel):
    email: Optional[str] = None


@router.post("/create-checkout")
async def create_checkout(body: CheckoutRequest = CheckoutRequest()):
    """Create a Stripe Checkout Session for Pro subscription.

    Works without authentication — identifies user by email.
    The webhook will upgrade the profile by email match.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Payments not configured")

    email = body.email or ""

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Email is required. Please provide your email address.",
        )

    # Check if already Pro
    db = get_service_client()
    profile = (
        db.table("profiles")
        .select("plan")
        .eq("email", email)
        .limit(1)
        .execute()
    )
    if profile.data and profile.data[0].get("plan") == "pro":
        raise HTTPException(status_code=400, detail="Already on Pro plan")

    base_url = "https://receipt-production-ebc4.up.railway.app"

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        customer_email=email,
        success_url=f"{base_url}/admin/pro.html?success=true",
        cancel_url=f"{base_url}/admin/pro.html",
        metadata={"email": email},
    )

    return {"checkout_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events (no auth — verified by signature)."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")

    db = get_service_client()

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email", "")
        user_id = session.get("metadata", {}).get("user_id")

        expires = datetime.now(timezone.utc) + timedelta(days=365)
        update_data = {
            "plan": "pro",
            "plan_expires_at": expires.isoformat(),
        }

        if user_id:
            db.table("profiles").update(update_data).eq("id", user_id).execute()
            log.info("Stripe: user %s upgraded to Pro (by id)", user_id)
            _award_deferred_referral(db, user_id)
        elif customer_email:
            db.table("profiles").update(update_data).eq(
                "email", customer_email
            ).execute()
            log.info("Stripe: user %s upgraded to Pro (by email)", customer_email)
            try:
                user_q = db.table("profiles").select("id").eq("email", customer_email).single().execute()
                if user_q.data:
                    _award_deferred_referral(db, user_q.data["id"])
            except Exception:
                pass

        # Send Pro welcome email
        if customer_email:
            try:
                await _send_pro_welcome_email(customer_email, expires)
            except Exception as e:
                log.warning("Stripe: welcome email failed for %s: %s", customer_email, e)

    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer", "")

        # Look up customer email from Stripe
        try:
            customer = stripe.Customer.retrieve(customer_id)
            email = customer.get("email", "")
            if email:
                db.table("profiles").update({
                    "plan": "free",
                    "plan_expires_at": None,
                }).eq("email", email).execute()
                log.info("Stripe: subscription cancelled for %s", email)
        except Exception as e:
            log.error("Stripe: failed to process cancellation: %s", e)

    return {"status": "ok"}


def _award_deferred_referral(db, user_id: str):
    """When a user upgrades to Pro, award deferred referral points to their referrer.

    PRO referrer: already got 25 pts at signup → now gets +25 = 50 total
    FREE referrer: got 0 pts at signup → now gets +50 = 50 total
    """
    try:
        profile = db.table("profiles").select(
            "referred_by"
        ).eq("id", user_id).single().execute()

        referred_by = (profile.data or {}).get("referred_by")
        if not referred_by:
            return  # Not referred by anyone

        # Find the referrer
        referrer = db.table("profiles").select(
            "id, points, plan"
        ).eq("referral_code", referred_by).single().execute()

        if not referrer.data:
            return

        current_pts = referrer.data.get("points") or 0
        referrer_plan = referrer.data.get("plan", "free")

        if referrer_plan == "pro":
            # PRO referrer already got 25 at signup → award remaining 25
            award = 25
        else:
            # FREE referrer got 0 at signup → award full 50
            award = 50

        db.table("profiles").update({
            "points": current_pts + award,
        }).eq("id", referrer.data["id"]).execute()
        log.info(
            "Deferred referral: awarded %d pts to %s referrer %s (referee %s went Pro)",
            award, referrer_plan.upper(), referrer.data["id"], user_id,
        )
    except Exception as e:
        log.warning("Deferred referral check failed: %s", e)


async def _send_pro_welcome_email(email: str, expires: datetime):
    """Send a welcome email when a user upgrades to Pro."""
    from app.services.email_service import send_email

    expires_str = expires.strftime("%B %d, %Y")

    html = f"""
    <div style="font-family:'Segoe UI',Helvetica,Arial,sans-serif;max-width:500px;margin:0 auto;
                background:#0d2818;color:#e8f5ec;padding:32px;border-radius:12px">
      <div style="text-align:center;margin-bottom:24px">
        <span style="font-size:48px">👑</span>
      </div>
      <h1 style="text-align:center;color:#7DDFAA;margin:0 0 8px;font-size:24px">
        Welcome to SmartDocket Pro!</h1>
      <p style="text-align:center;color:#a0c4ab;margin:0 0 24px;font-size:14px">
        Your upgrade is confirmed</p>
      <div style="background:rgba(255,255,255,0.06);border-radius:8px;padding:20px;margin-bottom:20px">
        <p style="margin:0 0 12px;font-size:15px"><strong style="color:#7DDFAA">✓ Unlimited receipt scans</strong></p>
        <p style="margin:0 0 12px;font-size:15px"><strong style="color:#7DDFAA">✓ Unlimited AI chat queries</strong></p>
        <p style="margin:0 0 12px;font-size:15px"><strong style="color:#7DDFAA">✓ Priority price alerts</strong></p>
        <p style="margin:0;font-size:15px"><strong style="color:#7DDFAA">✓ Advanced spending insights</strong></p>
      </div>
      <p style="font-size:13px;color:#a0c4ab;text-align:center">
        Your subscription is active until <strong style="color:#e8f5ec">{expires_str}</strong></p>
      <p style="font-size:12px;color:#6a8a72;text-align:center;margin-top:20px">
        Thank you for supporting SmartDocket! 💚</p>
    </div>
    """

    await send_email(email, "👑 Welcome to SmartDocket Pro!", html)
    log.info("Pro welcome email sent to %s", email)
