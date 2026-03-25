from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional


class ReceiptItemBase(BaseModel):
    raw_name: str
    normalized_name: str
    category: str
    brand: Optional[str] = None
    quantity: float = 1.0
    unit: Optional[str] = None
    unit_price: float
    total_price: float
    discount_amount: float = 0.0
    is_on_offer: bool = False
    barcode: Optional[str] = None


class CollectiveComparison(BaseModel):
    cheapest_store: str
    cheapest_price: float
    difference: float


class ReceiptItemResponse(ReceiptItemBase):
    id: UUID
    receipt_id: UUID
    collective_price: Optional[CollectiveComparison] = None


class ReceiptCreate(BaseModel):
    store_name: str
    store_branch: Optional[str] = None
    store_address: Optional[str] = None
    purchased_at: datetime
    total_amount: float
    subtotal: Optional[float] = None
    discount_total: float = 0.0
    items: list[ReceiptItemBase]


class ReceiptResponse(BaseModel):
    id: UUID
    user_id: UUID
    store_name: str
    store_branch: Optional[str] = None
    store_address: Optional[str] = None
    purchased_at: datetime
    total_amount: float
    subtotal: Optional[float] = None
    discount_total: float = 0.0
    image_url: Optional[str] = None
    status: str = "pending"
    source: str = "photo"
    items_count: Optional[int] = None
    error_reason: Optional[str] = None
    created_at: datetime


class ReceiptDetailResponse(ReceiptResponse):
    items: list[ReceiptItemResponse] = []
    raw_text: Optional[str] = None


class ReceiptStatusResponse(BaseModel):
    receipt_id: UUID
    status: str
    progress: int = 0
    message: str = ""


class ReceiptUploadResponse(BaseModel):
    receipt_id: UUID
    status: str = "processing"
    message: str = "Receipt is being processed. Check status in a few seconds."


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class ReceiptListResponse(BaseModel):
    data: list[ReceiptResponse]
    pagination: PaginationMeta
