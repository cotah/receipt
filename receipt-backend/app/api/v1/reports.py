from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from app.utils.auth_utils import get_current_user
from app.database import get_service_client
from app.services.report_service import generate_monthly_report, generate_yearly_overview

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/monthly")
async def get_monthly_report(
    month: str | None = Query(None, description="Format: 2026-03"),
    user_id: str = Depends(get_current_user),
):
    if month is None:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
    db = get_service_client()
    return await generate_monthly_report(db, user_id, month)


@router.get("/yearly-overview")
async def get_yearly_overview(user_id: str = Depends(get_current_user)):
    db = get_service_client()
    return await generate_yearly_overview(db, user_id)
