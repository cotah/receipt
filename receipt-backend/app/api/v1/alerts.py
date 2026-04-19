from fastapi import APIRouter, Depends, HTTPException
from app.database import get_service_client
from app.models.alert import AlertListResponse, AlertResponse
from app.services.attribution_service import confirm_saving
from app.utils.auth_utils import get_current_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    unread_only: bool = False,
    page: int = 1,
    per_page: int = 20,
    user_id: str = Depends(get_current_user),
):
    from datetime import datetime, timedelta, timezone
    db = get_service_client()

    # Only show alerts from last 30 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    # Unread count (last 30 days only)
    unread_resp = (
        db.table("alerts")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("is_read", False)
        .gte("created_at", cutoff)
        .execute()
    )
    unread_count = unread_resp.count or 0

    # Query alerts (last 30 days)
    query = (
        db.table("alerts")
        .select("*", count="exact")
        .eq("user_id", user_id)
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
    )
    if unread_only:
        query = query.eq("is_read", False)

    offset = (page - 1) * per_page
    query = query.range(offset, offset + per_page - 1)
    result = query.execute()

    alerts = [AlertResponse(**a) for a in (result.data or [])]
    return AlertListResponse(unread_count=unread_count, data=alerts)


@router.patch("/{alert_id}/read", status_code=200)
async def mark_as_read(
    alert_id: str,
    user_id: str = Depends(get_current_user),
):
    db = get_service_client()
    result = (
        db.table("alerts")
        .update({"is_read": True})
        .eq("id", alert_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "ok"}


@router.patch("/read-all", status_code=200)
async def mark_all_as_read(user_id: str = Depends(get_current_user)):
    db = get_service_client()
    db.table("alerts").update({"is_read": True}).eq("user_id", user_id).eq("is_read", False).execute()
    return {"status": "ok"}


@router.post("/{alert_id}/confirm-saving")
async def confirm_alert_saving(
    alert_id: str,
    user_id: str = Depends(get_current_user),
):
    """Confirm that the user acted on an alert and saved money."""
    db = get_service_client()
    result = await confirm_saving(db, user_id, alert_id)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail="Alert not eligible for confirmation "
            "(already confirmed, expired, or not found)",
        )
    return result
