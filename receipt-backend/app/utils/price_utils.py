from datetime import datetime, timezone


PERISHABLE_CATEGORIES = {"Fruit & Veg", "Bakery", "Meat & Fish"}
SEMI_PERISHABLE_CATEGORIES = {"Dairy", "Deli"}


def get_ttl_days(category: str) -> int:
    """Return price TTL in days based on product category."""
    if category in PERISHABLE_CATEGORIES:
        return 14
    if category in SEMI_PERISHABLE_CATEGORIES:
        return 21
    return 30


def is_price_expired(expires_at: datetime) -> bool:
    """Check if a price entry has expired."""
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return now > expires_at
