import pytest
from app.services.chat_service import build_system_prompt, CHAT_SYSTEM_PROMPT


def test_system_prompt_includes_user_context():
    context = {
        "month_total": 350.00,
        "month_receipts": 6,
        "prev_month_total": 400.00,
        "top_store": "Lidl",
        "product_count": 120,
        "recent_items_summary": "- Fruit & Veg: €45.00\n- Dairy: €30.00",
        "price_insights": "- Banana: bought 8 times, avg €1.05",
    }
    prompt = build_system_prompt(context)
    assert "€350.00" in prompt
    assert "6 shops" in prompt
    assert "Lidl" in prompt
    assert "Fruit & Veg" in prompt


def test_system_prompt_restricts_to_grocery():
    assert "grocery" in CHAT_SYSTEM_PROMPT.lower() or "spending" in CHAT_SYSTEM_PROMPT.lower()
    assert "ONLY" in CHAT_SYSTEM_PROMPT


def test_system_prompt_uses_euro():
    assert "€" in CHAT_SYSTEM_PROMPT
