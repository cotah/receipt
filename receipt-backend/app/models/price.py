from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional


class StorePrice(BaseModel):
    store_name: str
    unit_price: float
    is_on_offer: bool = False
    last_seen: datetime
    confirmations: int = 1
    is_cheapest: bool = False
    saving_vs_most_expensive: Optional[float] = None


class PriceCompareResponse(BaseModel):
    product_name: str
    unit: Optional[str] = None
    last_updated: datetime
    stores: list[StorePrice]


class BasketItem(BaseModel):
    store: str
    total_estimated: float
    items_available: int
    items_missing: int
    savings_vs_most_expensive: float = 0.0


class SplitRecommendation(BaseModel):
    message: str
    total_with_split: float


class BasketRequest(BaseModel):
    items: list[str]


class BasketResponse(BaseModel):
    summary: list[BasketItem]
    split_recommendation: Optional[SplitRecommendation] = None


class LeafletOffer(BaseModel):
    store: str
    product_name: str
    unit_price: float
    original_price: Optional[float] = None
    discount_percent: Optional[int] = None
    category: str
    valid_from: date
    valid_until: date


class LeafletOffersResponse(BaseModel):
    valid_until: Optional[date] = None
    offers: list[LeafletOffer]
