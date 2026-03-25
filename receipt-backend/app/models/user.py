from pydantic import BaseModel
from datetime import date, datetime
from uuid import UUID
from typing import Optional


class UserProfile(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    locale: str = "en-IE"
    currency: str = "EUR"
    home_area: Optional[str] = None
    notify_alerts: bool = True
    notify_reports: bool = True
    plan: str = "free"
    plan_expires_at: Optional[datetime] = None
    scans_this_month: int = 0
    chat_queries_today: int = 0
    points: int = 0
    referral_code: Optional[str] = None
    referred_by: Optional[str] = None
    is_admin: bool = False
    created_at: datetime
    updated_at: datetime


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    locale: Optional[str] = None
    home_area: Optional[str] = None
    notify_alerts: Optional[bool] = None
    notify_reports: Optional[bool] = None


class UserStats(BaseModel):
    member_since: date
    total_receipts: int = 0
    total_spent_lifetime: float = 0.0
    total_saved_lifetime: float = 0.0
    unique_products_tracked: int = 0
    contribution_count: int = 0
    top_store: Optional[str] = None
