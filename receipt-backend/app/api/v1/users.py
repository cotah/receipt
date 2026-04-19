import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
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
    result = db.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
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
    profile = db.table("profiles").select("created_at").eq("id", user_id).maybe_single().execute()
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
    """Redeem a referral code.

    - Referee (person using code): ALWAYS gets 50 points immediately.
    - Referrer: gets points based on plan.
    - Limit: each referral code can be used max 5 times per month.
    """
    db = get_service_client()
    code = body.referral_code.strip().upper()

    # Check current user hasn't already been referred
    me = db.table("profiles").select(
        "referred_by, referral_code"
    ).eq("id", user_id).maybe_single().execute()
    if not me.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    if me.data.get("referred_by"):
        raise HTTPException(status_code=400, detail="Already redeemed a referral code")
    if me.data.get("referral_code") == code:
        raise HTTPException(status_code=400, detail="Cannot use your own referral code")

    # Find referrer
    referrer = db.table("profiles").select(
        "id, points, plan"
    ).eq("referral_code", code).maybe_single().execute()
    if not referrer.data:
        raise HTTPException(status_code=404, detail="Invalid referral code")

    # Check referrer's monthly referral limit (5/month)
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    referrals_this_month = (
        db.table("profiles")
        .select("id", count="exact")
        .eq("referred_by", code)
        .gte("created_at", month_start.isoformat())
        .execute()
    )
    if (referrals_this_month.count or 0) >= 5:
        raise HTTPException(
            status_code=400,
            detail="This referral code has reached its monthly limit (5 per month). Try again next month."
        )

    referrer_id = referrer.data["id"]
    referrer_plan = referrer.data.get("plan", "free")

    # Referee ALWAYS gets 50 pts
    my_points_q = db.table("profiles").select(
        "points"
    ).eq("id", user_id).maybe_single().execute()
    my_points = ((my_points_q.data or {}).get("points") or 0) + 50

    db.table("profiles").update({
        "referred_by": code,
        "points": my_points,
    }).eq("id", user_id).execute()

    # Referrer rewards:
    # PRO referrer → 25 pts now (signup) + 25 pts when referee goes Pro = 50 total
    # FREE referrer → 0 pts now + 50 pts when referee goes Pro
    referrer_earned = 0
    if referrer_plan == "pro":
        referrer_points = (referrer.data.get("points") or 0) + 25
        db.table("profiles").update({
            "points": referrer_points,
        }).eq("id", referrer_id).execute()
        referrer_earned = 25
        log.info(
            "Referral redeemed: %s used code %s (PRO referrer %s). Referee +50, Referrer +25 now.",
            user_id, code, referrer_id,
        )
    else:
        log.info(
            "Referral redeemed: %s used code %s (FREE referrer %s). Referee +50 pts. Referrer deferred.",
            user_id, code, referrer_id,
        )

    return {
        "status": "ok",
        "points_earned": 50,
        "referrer_earned": referrer_earned,
        "referrer_deferred": True,
    }


@router.get("/me/contribute")
async def get_contribute_status(user_id: str = Depends(get_current_user)):
    """Gamification status — points, level, weekly challenge, leaderboard."""
    db = get_service_client()

    # Get user points
    profile = db.table("profiles").select(
        "points, scans_this_month, plan, created_at"
    ).eq("id", user_id).maybe_single().execute()
    points = (profile.data or {}).get("points") or 0
    scans = (profile.data or {}).get("scans_this_month") or 0

    # Level calculation
    if points >= 1000:
        level = {"name": "Price Master", "emoji": "🏆", "min": 1000}
    elif points >= 500:
        level = {"name": "Smart Shopper", "emoji": "⭐", "min": 500}
    elif points >= 200:
        level = {"name": "Bargain Hunter", "emoji": "🎯", "min": 200}
    elif points >= 100:
        level = {"name": "Saver", "emoji": "💚", "min": 100}
    elif points >= 25:
        level = {"name": "Newcomer", "emoji": "🌱", "min": 25}
    else:
        level = {"name": "Getting Started", "emoji": "👋", "min": 0}

    # Weekly challenge: scan X receipts this week
    challenge_target = 5
    challenge = {
        "title": "Price Hunter",
        "description": f"Scan & verify {challenge_target} products this week",
        "progress": min(scans, challenge_target),
        "target": challenge_target,
        "bonus_points": 100,
        "complete": scans >= challenge_target,
    }

    # How to earn points
    actions = [
        {"action": "Scan a receipt", "points": 1, "points_pro": 2, "icon": "camera", "description": "1pt per item (Free) or 2pt per item (Pro). Min 3/5, max 40/80 pts"},
        {"action": "Link barcodes", "points": 20, "points_pro": 30, "icon": "maximize", "description": "Link product barcodes after scanning a receipt"},
        {"action": "Add a new barcode", "points": 5, "points_pro": 10, "icon": "plus-circle", "description": "Scan a new product barcode (0 pts if already exists)"},
        {"action": "Refer a friend", "points": 50, "icon": "users", "description": "You and your friend both earn 50 pts (5 referrals/month max)"},
        {"action": "Confirm a saving", "points": 10, "icon": "thumbs-up", "description": "Confirm SmartDocket helped you save"},
        {"action": "Pro monthly bonus", "points": 200, "icon": "zap", "description": "Pro subscribers get 200 bonus points every month"},
    ]

    # Leaderboard — top 10 users by points this month
    try:
        top_users = (
            db.table("profiles")
            .select("id, full_name, points")
            .order("points", desc=True)
            .limit(10)
            .execute()
        )
        leaderboard = []
        my_rank = None
        for i, u in enumerate(top_users.data or []):
            name = u.get("full_name") or "Anonymous"
            # Abbreviate: "John Smith" → "John S."
            parts = name.split()
            display = f"{parts[0]} {parts[1][0]}." if len(parts) > 1 else parts[0]
            entry = {
                "rank": i + 1,
                "name": display,
                "points": u.get("points") or 0,
                "is_me": u["id"] == user_id,
            }
            leaderboard.append(entry)
            if u["id"] == user_id:
                my_rank = i + 1
    except Exception:
        leaderboard = []
        my_rank = None

    # Raffle info — 3 prizes, monthly draw
    from calendar import monthrange
    now = datetime.now(timezone.utc)

    # Next draw: first Saturday of next month
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1)
    else:
        next_month = now.replace(month=now.month + 1, day=1)
    first_sat = next_month
    while first_sat.weekday() != 5:  # 5 = Saturday
        first_sat += timedelta(days=1)

    raffle = {
        "prizes": [
            {"name": "Signed Premier League Jersey", "points_per_ticket": 1500, "emoji": "🥇", "my_tickets": points // 1500},
            {"name": "Gift Card Boots €30", "points_per_ticket": 1000, "emoji": "🥈", "my_tickets": points // 1000},
            {"name": "Supermarket Voucher €30", "points_per_ticket": 800, "emoji": "🥉", "my_tickets": points // 800},
        ],
        "next_draw": first_sat.strftime("%B %d, %Y"),
        "total_points": points,
    }

    return {
        "points": points,
        "level": level,
        "challenge": challenge,
        "actions": actions,
        "leaderboard": leaderboard,
        "my_rank": my_rank,
        "raffle": raffle,
    }


@router.post("/me/verify-price")
async def verify_price(
    product_key: str = Query(...),
    store_name: str = Query(...),
    user_id: str = Depends(get_current_user),
):
    """User confirms a price is still accurate — earns 5 points."""
    db = get_service_client()

    # Award points
    try:
        profile = db.table("profiles").select("points").eq("id", user_id).maybe_single().execute()
        current = (profile.data or {}).get("points") or 0
        db.table("profiles").update({"points": current + 5}).eq("id", user_id).execute()
    except Exception as e:
        log.warning("verify_price points error: %s", e)

    return {"status": "ok", "points_earned": 5}


@router.delete("/me")
async def delete_account(user_id: str = Depends(get_current_user)):
    """Permanently delete the user's account and all associated data.

    This endpoint:
    1. Deletes all user data from every table (explicit, even when CASCADE exists)
    2. Deletes the profile row
    3. Deletes the Supabase Auth user

    Apple App Store guideline 5.1.1(v) requires apps that support account
    creation to also support account deletion.
    """
    db = get_service_client()

    log.info("Account deletion requested for user %s", user_id)

    # --- 1. Delete user data from all tables (order: dependents first) ---
    tables_with_user_id = [
        "feedback",
        "shopping_list_items",
        "savings_attributions",
        "user_product_patterns",
        "chat_messages",
        "alerts",
        "receipt_items",
        "receipts",
    ]

    deleted_counts: dict[str, int] = {}
    for table in tables_with_user_id:
        try:
            result = db.table(table).delete().eq("user_id", user_id).execute()
            deleted_counts[table] = len(result.data) if result.data else 0
        except Exception as e:
            # Table might not exist or have no user_id column — skip silently
            log.warning("delete_account: skip table %s: %s", table, e)
            deleted_counts[table] = 0

    # --- 2. Delete the profile row ---
    try:
        db.table("profiles").delete().eq("id", user_id).execute()
        deleted_counts["profiles"] = 1
    except Exception as e:
        log.error("delete_account: failed to delete profile for %s: %s", user_id, e)
        raise HTTPException(status_code=500, detail="Failed to delete profile")

    # --- 3. Delete the Supabase Auth user ---
    try:
        db.auth.admin.delete_user(user_id)
        log.info("Account deletion completed for user %s — data: %s", user_id, deleted_counts)
    except Exception as e:
        log.error("delete_account: failed to delete auth user %s: %s", user_id, e)
        # Profile is already gone — don't block, but log the issue
        log.warning("Auth user %s may be orphaned — manual cleanup needed", user_id)

    return {"status": "deleted", "detail": "Account and all associated data have been permanently deleted."}
