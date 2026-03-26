"""Tests for search_service.py — grouping and normalization logic."""

import pytest
from app.services.search_service import (
    _normalize_for_grouping,
    _token_similarity,
    _group_products,
)


# --- Normalization ---

def test_normalize_strips_store_brand():
    assert _normalize_for_grouping("SuperValu Strawberries (325 g)") == "strawberries"


def test_normalize_strips_tesco_finest():
    # "tesco finest" is a store brand prefix, stripped entirely
    assert _normalize_for_grouping("Tesco Finest Sourdough Bread 400g") == "sourdough bread"


def test_normalize_strips_size_parentheses():
    assert _normalize_for_grouping("Bundys Brioche Burger Buns 4 Pack (320 g)") == "bundys brioche burger buns"


def test_normalize_strips_weight():
    assert _normalize_for_grouping("Nutella 400g") == "nutella"


def test_normalize_preserves_brand():
    result = _normalize_for_grouping("Bundys Brioche Burger Bun 4 Pack")
    assert "bundys" in result
    assert "brioche" in result


def test_normalize_case_insensitive():
    # "2L" is stripped as a size indicator
    result = _normalize_for_grouping("WHOLE MILK 2L")
    assert "whole milk" in result


# --- Token similarity ---

def test_similarity_identical():
    assert _token_similarity("bundys brioche", "bundys brioche") == 1.0


def test_similarity_partial():
    sim = _token_similarity("bundys brioche burger buns", "bundys brioche burger bun")
    assert sim >= 0.6  # Should match


def test_similarity_different():
    sim = _token_similarity("nutella chocolate", "avonmore milk")
    assert sim < 0.3


def test_similarity_empty():
    assert _token_similarity("", "something") == 0.0


# --- Product grouping ---

def test_group_same_product_different_stores():
    rows = [
        {"product_name": "Bundys Brioche Burger Buns 4 Pack (320 g)", "store_name": "SuperValu", "unit_price": "2.35", "is_on_offer": True, "observed_at": "2026-01-01", "product_key": "bundys_brioche_burger_buns_4_pack_320_g"},
        {"product_name": "Bundys Brioche Burger Bun 4 Pack", "store_name": "Tesco", "unit_price": "3.70", "is_on_offer": False, "observed_at": "2026-01-01", "product_key": "bundys_brioche_burger_bun_4_pack"},
    ]
    groups = _group_products(rows)
    # Should be grouped into 1 group with 2 stores
    assert len(groups) == 1
    assert len(groups[0]["stores"]) == 2
    # Cheapest first
    assert groups[0]["stores"][0]["unit_price"] == 2.35


def test_group_different_products():
    rows = [
        {"product_name": "Nutella 400g", "store_name": "Tesco", "unit_price": "4.50", "is_on_offer": False, "observed_at": "2026-01-01", "product_key": "nutella_400g"},
        {"product_name": "Whole Milk 2L", "store_name": "Lidl", "unit_price": "1.50", "is_on_offer": False, "observed_at": "2026-01-01", "product_key": "whole_milk_2l"},
    ]
    groups = _group_products(rows)
    assert len(groups) == 2


def test_group_keeps_cheapest_per_store():
    rows = [
        {"product_name": "Milk 1L", "store_name": "Tesco", "unit_price": "1.50", "is_on_offer": False, "observed_at": "2026-01-01", "product_key": "milk_1l"},
        {"product_name": "Milk 1L", "store_name": "Tesco", "unit_price": "1.20", "is_on_offer": True, "observed_at": "2026-01-01", "product_key": "milk_1l_offer"},
    ]
    groups = _group_products(rows)
    # Same store — should keep the cheaper one
    assert len(groups) == 1
    assert groups[0]["stores"][0]["unit_price"] == 1.20


def test_group_multi_store_first():
    rows = [
        {"product_name": "Bread", "store_name": "Tesco", "unit_price": "1.50", "is_on_offer": False, "observed_at": "2026-01-01", "product_key": "bread_tesco"},
        {"product_name": "Bread", "store_name": "Lidl", "unit_price": "1.20", "is_on_offer": False, "observed_at": "2026-01-01", "product_key": "bread_lidl"},
        {"product_name": "Exotic Fruit Juice", "store_name": "SuperValu", "unit_price": "0.50", "is_on_offer": False, "observed_at": "2026-01-01", "product_key": "exotic"},
    ]
    groups = _group_products(rows)
    # Multi-store group should come first even if single is cheaper
    assert len(groups[0]["stores"]) == 2
    assert groups[0]["stores"][0]["store_name"] == "Lidl"  # cheapest within group


def test_group_empty():
    assert _group_products([]) == []
