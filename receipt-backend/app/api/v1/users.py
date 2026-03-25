import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.utils.auth_utils import get_current_user
from app.database import get_service_client
from app.models.user import UserProfile, UserProfileUpdate, UserStats

log = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


def _generate_referral_code() -> str:
    """Generate a referral code like SMART-ABC123."""
    return f"SMART-{secrets.token_hex(3).upper()}"


def _ensure_referral_code(db, user_id: str, profile_data: dict) -> dict:
    """If the profile has no referral_code, generate and save one."""
    if not profile_data.get("referral_code"):
        code = _generate_referral_code()
        db.table("profiles").update(
            {"referral_code": code}
        ).eq("id", user_id).execute()
        profile_data["referral_code"] = code
    return profile_data


@router.get("/me", response_model=UserProfile)
async def get_profile(user_id: str = Depends(get_current_user)):
    db = get_service_client()
    result = db.table("profiles").select("*").eq("id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    data = _ensure_referral_code(db, user_id, result.data)
    return UserProfile(**data)


@router.patch("/me", response_model=UserProfile)
async def update_profile(
    body: UserProfileUpdate,
    user_id: str = Depends(get_current_user),
):
    db = get_service_client()
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = (
        db.table("profiles")
        .update(update_data)
        .eq("id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    return UserProfile(**result.data[0])


@router.get("/me/stats", response_model=UserStats)
async def get_stats(user_id: str = Depends(get_current_user)):
    db = get_service_client()

    # Profile for member_since
    profile = db.table("profiles").select("created_at").eq("id", user_id).single().execute()
    member_since = profile.data["created_at"][:10] if profile.data else "2026-01-01"

    # Receipts
    receipts = (
        db.table("receipts")
        .select("total_amount, discount_total, store_name", count="exact")
        .eq("user_id", user_id)
        .eq("status", "done")
        .execute()
    )
    receipt_data = receipts.data or []
    total_receipts = receipts.count or 0
    total_spent = sum(r["total_amount"] for r in receipt_data)
    total_saved = sum(r.get("discount_total", 0) for r in receipt_data)

    # Top store
    store_counts: dict[str, int] = {}
    for r in receipt_data:
        store_counts[r["store_name"]] = store_counts.get(r["store_name"], 0) + 1
    top_store = max(store_counts, key=store_counts.get) if store_counts else None

    # Unique products
    products = (
        db.table("receipt_items")
        .select("normalized_name")
        .eq("user_id", user_id)
        .execute()
    )
    unique_products = len(set(p["normalized_name"] for p in (products.data or [])))

    # Contributions (approximate via receipt items count)
    items_count = (
        db.table("receipt_items")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    contribution_count = items_count.count or 0

    return UserStats(
        member_since=member_since,
        total_receipts=total_receipts,
        total_spent_lifetime=round(total_spent, 2),
        total_saved_lifetime=round(total_saved, 2),
        unique_products_tracked=unique_products,
        contribution_count=contribution_count,
        top_store=top_store,
    )


class RedeemReferralRequest(BaseModel):
    referral_code: str


@router.post("/me/redeem-referral")
async def redeem_referral(
    body: RedeemReferralRequest,
    user_id: str = Depends(get_current_user),
):
    """Redeem a referral code. Both referrer and referee get 50 points."""
    db = get_service_client()
    code = body.referral_code.strip().upper()

    # Check current user hasn't already been referred
    me = db.table("profiles").select(
        "referred_by, referral_code"
    ).eq("id", user_id).single().execute()
    if not me.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    if me.data.get("referred_by"):
        raise HTTPException(status_code=400, detail="Already redeemed a referral code")
    if me.data.get("referral_code") == code:
        raise HTTPException(status_code=400, detail="Cannot use your own referral code")

    # Find referrer
    referrer = db.table("profiles").select(
        "id, points"
    ).eq("referral_code", code).single().execute()
    if not referrer.data:
        raise HTTPException(status_code=404, detail="Invalid referral code")

    referrer_id = referrer.data["id"]
    referrer_points = (referrer.data.get("points") or 0) + 50

    # Get current user points
    my_points_q = db.table("profiles").select(
        "points"
    ).eq("id", user_id).single().execute()
    my_points = ((my_points_q.data or {}).get("points") or 0) + 50

    # Update both
    db.table("profiles").update({
        "referred_by": code,
        "points": my_points,
    }).eq("id", user_id).execute()

    db.table("profiles").update({
        "points": referrer_points,
    }).eq("id", referrer_id).execute()

    log.info(
        "Referral redeemed: %s used code %s (referrer %s). +50 pts each.",
        user_id, code, referrer_id,
    )

    return {"status": "ok", "points_earned": 50}
