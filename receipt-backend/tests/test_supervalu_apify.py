"""Tests for SuperValu Apify integration in leaflet_worker.py."""

import re
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.utils.text_utils import generate_product_key


# ---------------------------------------------------------------------------
# _save_supervalu_apify_items tests
# ---------------------------------------------------------------------------


def _make_mock_db():
    """Create a mock Supabase client for testing."""
    db = MagicMock()
    db.table.return_value.upsert.return_value.execute.return_value = MagicMock()
    return db


def test_save_supervalu_apify_items_basic():
    """Valid Apify items are saved correctly."""
    from app.workers.leaflet_worker import _save_supervalu_apify_items

    db = _make_mock_db()
    items = [
        {"name": "Bananas (5 Pack)", "price": "€1.50", "promotion": "3 for €4", "page": 1},
        {"name": "Milk 2L", "price": "€1.89", "promotion": None, "page": 1},
    ]
    count = _save_supervalu_apify_items(db, items)
    assert count == 2
    assert db.table.return_value.upsert.call_count == 2

    # Verify first item was saved with correct data
    first_call_args = db.table.return_value.upsert.call_args_list[0]
    saved_data = first_call_args[0][0]
    assert saved_data["product_name"] == "Bananas (5 Pack)"
    assert saved_data["unit_price"] == 1.50
    assert saved_data["store_name"] == "SuperValu"
    assert saved_data["is_on_offer"] is True
    assert saved_data["source"] == "leaflet"


def test_save_supervalu_apify_items_cleans_name():
    """'Open Product Description' is stripped from names."""
    from app.workers.leaflet_worker import _save_supervalu_apify_items

    db = _make_mock_db()
    items = [
        {"name": "All Butter Croissant (70 g)Open Product Description", "price": "€1.40", "promotion": "4 for €4.50", "page": 1},
    ]
    count = _save_supervalu_apify_items(db, items)
    assert count == 1
    saved_data = db.table.return_value.upsert.call_args_list[0][0][0]
    assert "Open Product Description" not in saved_data["product_name"]
    assert saved_data["product_name"] == "All Butter Croissant (70 g)"


def test_save_supervalu_apify_items_comma_price():
    """European format prices (€3,50) are handled."""
    from app.workers.leaflet_worker import _save_supervalu_apify_items

    db = _make_mock_db()
    items = [
        {"name": "Cheese Wheel", "price": "€3,50", "promotion": None, "page": 2},
    ]
    count = _save_supervalu_apify_items(db, items)
    assert count == 1
    saved_data = db.table.return_value.upsert.call_args_list[0][0][0]
    assert saved_data["unit_price"] == 3.50


def test_save_supervalu_apify_items_skips_missing_name():
    """Items without name are skipped."""
    from app.workers.leaflet_worker import _save_supervalu_apify_items

    db = _make_mock_db()
    items = [
        {"name": "", "price": "€1.50", "promotion": None, "page": 1},
        {"name": None, "price": "€2.00", "promotion": None, "page": 1},
        {"price": "€3.00", "promotion": None, "page": 1},  # no name key
    ]
    count = _save_supervalu_apify_items(db, items)
    assert count == 0


def test_save_supervalu_apify_items_skips_missing_price():
    """Items without parseable price are skipped."""
    from app.workers.leaflet_worker import _save_supervalu_apify_items

    db = _make_mock_db()
    items = [
        {"name": "Bread", "price": "", "promotion": None, "page": 1},
        {"name": "Milk", "price": "free", "promotion": None, "page": 1},
        {"name": "Eggs", "promotion": None, "page": 1},  # no price key
    ]
    count = _save_supervalu_apify_items(db, items)
    assert count == 0


def test_save_supervalu_apify_items_is_on_offer():
    """is_on_offer is True when promotion is present, False otherwise."""
    from app.workers.leaflet_worker import _save_supervalu_apify_items

    db = _make_mock_db()
    items = [
        {"name": "Yoghurt", "price": "€2.00", "promotion": "2 for €3", "page": 1},
        {"name": "Butter", "price": "€3.50", "promotion": None, "page": 1},
    ]
    count = _save_supervalu_apify_items(db, items)
    assert count == 2
    # First item (with promotion) should be on_offer=True
    first = db.table.return_value.upsert.call_args_list[0][0][0]
    assert first["is_on_offer"] is True
    # Second item (no promotion) should be on_offer=False
    second = db.table.return_value.upsert.call_args_list[1][0][0]
    assert second["is_on_offer"] is False


def test_save_supervalu_apify_items_upsert_conflict():
    """Upsert uses correct on_conflict constraint."""
    from app.workers.leaflet_worker import _save_supervalu_apify_items

    db = _make_mock_db()
    items = [
        {"name": "Bread", "price": "€1.50", "promotion": None, "page": 1},
    ]
    _save_supervalu_apify_items(db, items)
    call_kwargs = db.table.return_value.upsert.call_args_list[0][1]
    assert call_kwargs["on_conflict"] == "product_key,store_name,source"


def test_save_supervalu_apify_items_product_key():
    """Product key is generated correctly."""
    from app.workers.leaflet_worker import _save_supervalu_apify_items

    db = _make_mock_db()
    items = [
        {"name": "SuperValu Strawberries (325 g)", "price": "€4.49", "promotion": "3 for €10", "page": 1},
    ]
    _save_supervalu_apify_items(db, items)
    saved_data = db.table.return_value.upsert.call_args_list[0][0][0]
    expected_key = generate_product_key("SuperValu Strawberries (325 g)")
    assert saved_data["product_key"] == expected_key


def test_save_supervalu_apify_items_empty_list():
    """Empty item list returns 0."""
    from app.workers.leaflet_worker import _save_supervalu_apify_items

    db = _make_mock_db()
    count = _save_supervalu_apify_items(db, [])
    assert count == 0
    assert db.table.return_value.upsert.call_count == 0


def test_save_supervalu_apify_items_db_error_continues():
    """DB errors on individual items don't stop processing."""
    from app.workers.leaflet_worker import _save_supervalu_apify_items

    db = _make_mock_db()
    # First upsert fails, second succeeds
    db.table.return_value.upsert.return_value.execute.side_effect = [
        Exception("DB error"),
        MagicMock(),
    ]
    items = [
        {"name": "Item 1", "price": "€1.00", "promotion": None, "page": 1},
        {"name": "Item 2", "price": "€2.00", "promotion": None, "page": 1},
    ]
    count = _save_supervalu_apify_items(db, items)
    assert count == 1  # Only second item saved


# ---------------------------------------------------------------------------
# SuperValu scraper threshold test
# ---------------------------------------------------------------------------


def test_supervalu_threshold_constant():
    """SuperValu HTML scraper has a minimum threshold that triggers Apify."""
    # This verifies the threshold exists in the code
    import ast
    with open("app/workers/leaflet_worker.py") as f:
        source = f.read()
    # Should find 'total_saved >= 100' (threshold for SuperValu)
    assert "total_saved >= 100" in source, (
        "SuperValu HTML scraper should have threshold >= 100 to trigger Apify fallback"
    )
