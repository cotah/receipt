from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional, Literal


class AlertResponse(BaseModel):
    id: UUID
    type: Literal["restock", "price_drop", "price_spike", "weekly_report"]
    product_name: Optional[str] = None
    store_name: Optional[str] = None
    message: str
    data: Optional[dict] = None
    is_read: bool = False
    created_at: datetime


class AlertListResponse(BaseModel):
    unread_count: int = 0
    data: list[AlertResponse]
