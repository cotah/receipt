from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, Literal


class PricePoint(BaseModel):
    date: str
    store: str
    price: float
    unit: Optional[str] = None


class PriceExtreme(BaseModel):
    price: float
    store: str
    date: str


class ProductHistory(BaseModel):
    product_name: str
    category: str
    purchase_count: int
    avg_days_between_purchases: Optional[float] = None
    predicted_next_purchase: Optional[date] = None
    price_history: list[PricePoint] = []
    avg_price: float
    cheapest_ever: Optional[PriceExtreme] = None
    most_expensive_ever: Optional[PriceExtreme] = None


class CategorySummary(BaseModel):
    name: str
    total_spent: float
    percentage: float
    items_count: int
    trend: str = "stable"
    trend_percent: float = 0.0


class CategoriesResponse(BaseModel):
    period: str
    categories: list[CategorySummary]


class BestPrice(BaseModel):
    store: str
    price: float


class RunningLowItem(BaseModel):
    product_name: str
    last_purchased: datetime
    avg_days_cycle: float
    days_since_last: int
    overdue_by_days: int
    urgency: Literal["low", "medium", "high"]
    typical_store: Optional[str] = None
    typical_price: Optional[float] = None
    best_current_price: Optional[BestPrice] = None


class RunningLowResponse(BaseModel):
    items: list[RunningLowItem]
