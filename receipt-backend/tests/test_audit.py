"""Audit tests — added during SmartDocket technical audit (30 March 2026).

Covers: plan_utils, rate_limit, feedback validation, shopping_list edge cases,
user referral edge cases, admin key verification, image validation, text_utils.
"""

import time
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.main import app
from app.utils.plan_utils import (
    is_pro,
    check_scan_limit,
    check_chat_limit,
    FREE_SCANS_PER_MONTH,
    FREE_CHAT_QUERIES_PER_DAY,
)
from app.utils.image_utils import validate_image
from app.utils.text_utils import generate_product_key, normalize_product_name

client = TestClient(app)

MOCK_USER_ID = "00000000-0000-0000-0000-000000000001"


def auth_override():
    return MOCK_USER_ID


@pytest.fixture(autouse=True)
def override_auth():
    from app.utils.auth_utils import get_current_user
    app.dependency_overrides[get_current_user] = auth_override
    yield
    app.dependency_overrides.clear()


# ==============================================================
# plan_utils — Free/Pro Plan Logic
# ==============================================================

class TestIsPro:
    def test_free_plan(self):
        assert is_pro({"plan": "free"}) is False

    def test_pro_no_expiry(self):
        """Pro plan without expiration date is NOT pro."""
        assert is_pro({"plan": "pro", "plan_expires_at": None}) is False

    def test_pro_expired(self):
        """Pro plan with past expiration is NOT pro."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        assert is_pro({"plan": "pro", "plan_expires_at": past}) is False

    def test_pro_active(self):
        """Pro plan with future expiration IS pro."""
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        assert is_pro({"plan": "pro", "plan_expires_at": future}) is True

    def test_pro_expires_today_still_active(self):
        """Pro plan expiring later today IS still pro."""
        later = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        assert is_pro({"plan": "pro", "plan_expires_at": later}) is True

    def test_empty_profile(self):
        """Empty profile dict defaults to free."""
        assert is_pro({}) is False


class TestScanLimit:
    def test_pro_no_limit(self):
        """Pro users have no scan limit."""
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        profile = {
            "plan": "pro",
            "plan_expires_at": future,
            "scans_this_month": 999,
        }
        # Should not raise
        check_scan_limit(MagicMock(), "user-1", profile)

    def test_free_under_limit(self):
        """Free user under limit passes."""
        profile = {
            "plan": "free",
            "scans_this_month": FREE_SCANS_PER_MONTH - 1,
            "scans_month_reset": date.today().replace(day=1).isoformat(),
        }
        check_scan_limit(MagicMock(), "user-1", profile)

    def test_free_at_limit_raises_402(self):
        """Free user at limit gets 402."""
        profile = {
            "plan": "free",
            "scans_this_month": FREE_SCANS_PER_MONTH,
            "scans_month_reset": date.today().replace(day=1).isoformat(),
        }
        with pytest.raises(HTTPException) as exc:
            check_scan_limit(MagicMock(), "user-1", profile)
        assert exc.value.status_code == 402

    def test_free_resets_on_new_month(self):
        """Counter resets when month changes."""
        mock_db = MagicMock()
        last_month = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)
        profile = {
            "plan": "free",
            "scans_this_month": FREE_SCANS_PER_MONTH,
            "scans_month_reset": last_month.isoformat(),
        }
        # Should not raise — counter resets
        check_scan_limit(mock_db, "user-1", profile)
        # Should have called update to reset counter
        mock_db.table.assert_called()


class TestChatLimit:
    def test_free_at_limit_raises_402(self):
        """Free user at daily chat limit gets 402."""
        profile = {
            "plan": "free",
            "chat_queries_today": FREE_CHAT_QUERIES_PER_DAY,
            "chat_queries_reset": date.today().isoformat(),
        }
        with pytest.raises(HTTPException) as exc:
            check_chat_limit(MagicMock(), "user-1", profile)
        assert exc.value.status_code == 402

    def test_free_resets_next_day(self):
        """Chat counter resets on a new day."""
        mock_db = MagicMock()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        profile = {
            "plan": "free",
            "chat_queries_today": FREE_CHAT_QUERIES_PER_DAY,
            "chat_queries_reset": yesterday,
        }
        # Should not raise — counter resets
        check_chat_limit(mock_db, "user-1", profile)


# ==============================================================
# Image Validation
# ==============================================================

class TestImageValidation:
    def test_valid_jpeg(self):
        assert validate_image("image/jpeg", 1024, 10) is None

    def test_valid_png(self):
        assert validate_image("image/png", 1024, 10) is None

    def test_valid_pdf(self):
        assert validate_image("application/pdf", 1024, 10) is None

    def test_invalid_type(self):
        result = validate_image("text/plain", 1024, 10)
        assert result is not None
        assert "Invalid file type" in result

    def test_too_large(self):
        result = validate_image("image/jpeg", 11 * 1024 * 1024, 10)
        assert result is not None
        assert "too large" in result

    def test_svg_rejected(self):
        """SVG could contain scripts — should be rejected."""
        result = validate_image("image/svg+xml", 1024, 10)
        assert result is not None

    def test_zero_size_ok(self):
        """Zero bytes technically valid type, content check happens later."""
        assert validate_image("image/jpeg", 0, 10) is None


# ==============================================================
# Text Utils — Product Key Generation
# ==============================================================

class TestProductKey:
    def test_simple(self):
        assert generate_product_key("Banana") == "banana"

    def test_with_unit(self):
        assert generate_product_key("Banana", "kg") == "banana_kg"

    def test_special_chars_stripped(self):
        key = generate_product_key("Ben & Jerry's Ice Cream")
        assert "&" not in key
        assert "'" not in key
        assert key == "ben_cream_ice_jerry_s"

    def test_unicode_normalized(self):
        key = generate_product_key("Café Latte")
        assert key == "cafe_latte"

    def test_empty_string(self):
        assert generate_product_key("") == ""

    def test_whitespace_only(self):
        assert generate_product_key("   ") == ""

    def test_numbers_preserved(self):
        key = generate_product_key("7up 500ml")
        assert "7up" in key


class TestNormalizeProductName:
    def test_title_case(self):
        assert normalize_product_name("whole milk") == "Whole Milk"

    def test_strips_whitespace(self):
        assert normalize_product_name("  Bread  ") == "Bread"

    def test_strips_receipt_codes(self):
        result = normalize_product_name("WHOLE MILK LH 2L")
        assert "LH" not in result


# ==============================================================
# Feedback — Input Validation
# ==============================================================

class TestFeedback:
    @patch("app.api.v1.feedback.get_service_client")
    @patch("app.api.v1.feedback.send_email")
    def test_too_short_message(self, mock_email, mock_db):
        """Reject messages shorter than 5 chars."""
        response = client.post(
            "/api/v1/feedback",
            json={"message": "hi", "category": "bug"},
        )
        assert response.status_code == 400
        assert "too short" in response.json()["detail"]

    @patch("app.api.v1.feedback.get_service_client")
    @patch("app.api.v1.feedback.send_email")
    def test_empty_message(self, mock_email, mock_db):
        """Reject empty messages."""
        response = client.post(
            "/api/v1/feedback",
            json={"message": "", "category": "bug"},
        )
        assert response.status_code == 400

    @patch("app.api.v1.feedback.get_service_client")
    @patch("app.api.v1.feedback.send_email", new_callable=AsyncMock)
    def test_valid_feedback(self, mock_email, mock_db):
        """Accept valid feedback and save to DB."""
        # Mock profile query
        mock_profile = MagicMock()
        mock_profile.data = {"email": "test@test.com", "full_name": "Test User"}
        mock_db.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_profile

        # Mock insert
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock()
        mock_db.return_value.table.return_value.insert.return_value = mock_insert

        response = client.post(
            "/api/v1/feedback",
            json={"message": "This is a valid bug report", "category": "bug"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "sent"


# ==============================================================
# Admin Key Verification
# ==============================================================

class TestAdminKey:
    def test_verify_admin_key_open_when_unconfigured(self):
        """ISSUE-004: When ADMIN_KEY is empty, debug endpoints are OPEN."""
        from app.main import _verify_admin_key
        from app.config import settings
        original = settings.ADMIN_KEY
        try:
            settings.ADMIN_KEY = ""
            mock_request = MagicMock()
            mock_request.headers = MagicMock()
            mock_request.headers.get.return_value = "anything"
            _verify_admin_key(mock_request)  # No exception = open access
        finally:
            settings.ADMIN_KEY = original

    def test_verify_admin_key_rejects_wrong_key(self):
        """With ADMIN_KEY configured, wrong key is rejected."""
        from app.main import _verify_admin_key
        from app.config import settings
        original = settings.ADMIN_KEY
        try:
            settings.ADMIN_KEY = "correct-secret-key"
            mock_request = MagicMock()
            mock_request.headers = MagicMock()
            mock_request.headers.get.return_value = "wrong-key"
            with pytest.raises(HTTPException) as exc:
                _verify_admin_key(mock_request)
            assert exc.value.status_code == 403
        finally:
            settings.ADMIN_KEY = original

    def test_verify_admin_key_accepts_correct_key(self):
        """With ADMIN_KEY configured, correct key is accepted."""
        from app.main import _verify_admin_key
        from app.config import settings
        original = settings.ADMIN_KEY
        try:
            settings.ADMIN_KEY = "correct-secret-key"
            mock_request = MagicMock()
            mock_request.headers = MagicMock()
            mock_request.headers.get.return_value = "correct-secret-key"
            _verify_admin_key(mock_request)  # No exception = accepted
        finally:
            settings.ADMIN_KEY = original

    def test_health_no_auth(self):
        """Health endpoint requires no auth."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


# ==============================================================
# Shopping List — Edge Cases
# ==============================================================

class TestShoppingList:
    @patch("app.api.v1.shopping_list.get_service_client")
    def test_get_empty_list(self, mock_db):
        """Empty shopping list returns proper structure."""
        mock_items = MagicMock()
        mock_items.data = []
        mock_checked = MagicMock()
        mock_checked.count = 0

        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.order.return_value.execute.return_value = mock_items
        mock_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_checked

        mock_db.return_value.table.return_value = mock_table

        response = client.get("/api/v1/shopping-list")
        assert response.status_code == 200
        data = response.json()
        assert data["total_items"] == 0
        assert data["estimated_total"] == 0.0

    @patch("app.api.v1.shopping_list.get_service_client")
    def test_add_item_duplicate_check(self, mock_db):
        """Adding an existing item returns 'exists' status."""
        mock_existing = MagicMock()
        mock_existing.data = [{"id": "item-1"}]
        mock_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_existing

        response = client.post(
            "/api/v1/shopping-list/add",
            json={"product_name": "Milk", "store_name": "Tesco", "unit_price": 1.50},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "exists"


# ==============================================================
# Rate Limit Middleware — Unit Tests
# ==============================================================

class TestRateLimit:
    def test_rate_limit_check_allows_normal_traffic(self):
        """Normal traffic under limit is allowed."""
        from app.middleware.rate_limit import _check_rate, _buckets
        # Clear any existing state
        key = "test:normal"
        _buckets[key] = []
        assert _check_rate(key, 10, 60) is True

    def test_rate_limit_check_blocks_excess(self):
        """Traffic over limit is blocked."""
        from app.middleware.rate_limit import _check_rate, _buckets
        key = "test:excess"
        # Fill to limit
        _buckets[key] = [time.time()] * 5
        assert _check_rate(key, 5, 60) is False

    def test_rate_limit_expires_old(self):
        """Old entries are cleaned up."""
        from app.middleware.rate_limit import _check_rate, _buckets
        key = "test:expire"
        # Add entries from 2 minutes ago (outside 60s window)
        old_time = time.time() - 120
        _buckets[key] = [old_time] * 10
        assert _check_rate(key, 5, 60) is True


# ==============================================================
# Users — Referral Edge Cases
# ==============================================================

class TestReferral:
    @patch("app.api.v1.users.get_service_client")
    def test_self_referral_rejected(self, mock_db):
        """Cannot use own referral code."""
        mock_me = MagicMock()
        mock_me.data = {"referred_by": None, "referral_code": "SMART-ABC123"}
        mock_db.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_me

        response = client.post(
            "/api/v1/users/me/redeem-referral",
            json={"referral_code": "SMART-ABC123"},
        )
        assert response.status_code == 400
        assert "own referral" in response.json()["detail"].lower()

    @patch("app.api.v1.users.get_service_client")
    def test_already_referred_rejected(self, mock_db):
        """Cannot redeem if already referred."""
        mock_me = MagicMock()
        mock_me.data = {"referred_by": "SMART-OLDCODE", "referral_code": "SMART-MYCODE"}
        mock_db.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_me

        response = client.post(
            "/api/v1/users/me/redeem-referral",
            json={"referral_code": "SMART-NEWCODE"},
        )
        assert response.status_code == 400
        assert "already" in response.json()["detail"].lower()


# ==============================================================
# Catalog Worker — Tesco IE data mapping
# ==============================================================
