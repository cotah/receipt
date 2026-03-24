from fastapi import APIRouter, Depends, HTTPException
from app.utils.auth_utils import get_current_user
from app.database import get_service_client
from app.models.user import UserProfile, UserProfileUpdate, UserStats

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserProfile)
async def get_profile(user_id: str = Depends(get_current_user)):
    db = get_service_client()
    result = db.table("profiles").select("*").eq("id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    return UserProfile(**result.data)


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
