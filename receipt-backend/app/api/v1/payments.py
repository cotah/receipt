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
        elif customer_email:
            db.table("profiles").update(update_data).eq(
                "email", customer_email
            ).execute()
            log.info("Stripe: user %s upgraded to Pro (by email)", customer_email)

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
