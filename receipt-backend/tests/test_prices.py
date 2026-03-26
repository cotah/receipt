import pytest
from datetime import datetime, timedelta, timezone
from app.utils.price_utils import get_ttl_days, is_price_expired


def test_price_ttl_perishables_14_days():
    assert get_ttl_days("Fruit & Veg") == 14
    assert get_ttl_days("Meat & Fish") == 14


def test_price_ttl_dairy_21_days():
    assert get_ttl_days("Dairy") == 21


def test_price_ttl_dry_goods_30_days():
    assert get_ttl_days("Household") == 30
    assert get_ttl_days("Snacks & Confectionery") == 30


def test_is_price_expired_future():
    future = datetime.now(timezone.utc) + timedelta(days=5)
    assert is_price_expired(future) is False


def test_is_price_expired_past():
    past = datetime.now(timezone.utc) - timedelta(days=1)
    assert is_price_expired(past) is True


def test_is_price_expired_naive_datetime():
    past = datetime.now() - timedelta(days=1)
    assert is_price_expired(past) is True
