import pytest
from app.utils.text_utils import normalize_product_name, generate_product_key
from app.utils.price_utils import get_ttl_days


def test_normalize_product_name_removes_receipt_codes():
    assert normalize_product_name("BANANAS LH KG") == "Bananas"


def test_normalize_product_name_title_case():
    assert normalize_product_name("WHOLE MILK 2L") == "Whole Milk 2L"


def test_normalize_product_name_strips_whitespace():
    assert normalize_product_name("  BREAD   SLICED  ") == "Bread Sliced"


def test_generate_product_key_simple():
    assert generate_product_key("Banana", "kg") == "banana_kg"


def test_generate_product_key_no_unit():
    assert generate_product_key("Bread Sliced") == "bread_sliced"


def test_generate_product_key_special_chars():
    key = generate_product_key("Müller's Yoghurt", "unit")
    # ü→u via NFKD, apostrophe ' → _ (non-alphanumeric = separator)
    assert key == "muller_s_yoghurt_unit"


def test_price_ttl_perishables():
    assert get_ttl_days("Fruit & Veg") == 14
    assert get_ttl_days("Bakery") == 14
    assert get_ttl_days("Meat & Fish") == 14


def test_price_ttl_dairy():
    assert get_ttl_days("Dairy") == 21
    assert get_ttl_days("Deli") == 21


def test_price_ttl_dry_goods():
    assert get_ttl_days("Household") == 30
    assert get_ttl_days("Drinks") == 30
    assert get_ttl_days("Other") == 30
