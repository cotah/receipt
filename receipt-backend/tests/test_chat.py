import pytest
from app.services.chat_service import build_system_prompt, CHAT_SYSTEM_PROMPT


def test_system_prompt_includes_user_context():
    context = {
        "user_name": "Henrique",
        "current_hour_utc": 12,
        "month_total": 350.00,
        "month_receipts": 6,
        "prev_month_total": 400.00,
        "top_store": "Lidl",
        "store_summary": "€200 at Lidl, €150 at Tesco",
        "full_items_this_month": "- Lidl | Banana | qty: 3 | €1.05",
        "store_prices": "Lidl: Banana 1kg — €1.05",
    }
    prompt = build_system_prompt(context)
    assert "€350.00" in prompt
    assert "6 shops" in prompt
    assert "Lidl" in prompt
    assert "Banana" in prompt
    assert "Henrique" in prompt


def test_system_prompt_restricts_to_grocery():
    assert "grocery" in CHAT_SYSTEM_PROMPT.lower() or "spending" in CHAT_SYSTEM_PROMPT.lower()


def test_system_prompt_uses_euro():
    assert "€" in CHAT_SYSTEM_PROMPT
