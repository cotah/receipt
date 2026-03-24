import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call
from fastapi.testclient import TestClient
from app.main import app
from app.api.v1.receipts import process_receipt_async

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


def test_upload_invalid_file():
    """Reject non-image files."""
    response = client.post(
        "/api/v1/receipts/upload",
        files={"file": ("test.txt", b"hello world", "text/plain")},
        data={"source": "photo"},
    )
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


def test_upload_too_large():
    """Reject files over max size."""
    large_content = b"x" * (11 * 1024 * 1024)  # 11MB
    response = client.post(
        "/api/v1/receipts/upload",
        files={"file": ("large.jpg", large_content, "image/jpeg")},
        data={"source": "photo"},
    )
    assert response.status_code == 400
    assert "too large" in response.json()["detail"]


@patch("app.api.v1.receipts.get_service_client")
def test_list_receipts(mock_db):
    """List receipts returns paginated response."""
    mock_result = MagicMock()
    mock_result.data = []
    mock_result.count = 0
    mock_db.return_value.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = mock_result

    response = client.get("/api/v1/receipts")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "pagination" in data


@patch("app.api.v1.receipts.get_service_client")
def test_get_receipt_not_found(mock_db):
    """Return 404 for non-existent receipt."""
    mock_result = MagicMock()
    mock_result.data = None
    mock_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_result

    response = client.get("/api/v1/receipts/non-existent-id")
    assert response.status_code == 404


@patch("app.api.v1.receipts.get_service_client")
def test_delete_receipt_not_found(mock_db):
    """Return 404 when deleting non-existent receipt."""
    mock_result = MagicMock()
    mock_result.data = None
    mock_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_result

    response = client.delete("/api/v1/receipts/non-existent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
@patch("app.api.v1.receipts.get_service_client")
@patch("app.services.embedding_service.store_item_embedding", new_callable=AsyncMock)
@patch("app.services.price_service.contribute_anonymous_price", new_callable=AsyncMock)
@patch("app.services.extraction_service.extract_receipt_data", new_callable=AsyncMock)
@patch("app.services.ocr_service.extract_text_from_image", new_callable=AsyncMock)
@patch("app.utils.pdf_utils.extract_text_from_pdf")
async def test_pdf_text_extraction_used_for_digital_pdf(
    mock_pdfplumber, mock_ocr, mock_extract, mock_price, mock_embed, mock_db
):
    """Digital PDF with enough text skips Gemini OCR and uses pdfplumber."""
    # pdfplumber returns sufficient text (>100 chars)
    pdf_text = "Lidl\n2026-01-15\nBananas 1.29\nMilk 0.99\nBread 1.49\nTotal 3.77\n" * 3
    mock_pdfplumber.return_value = pdf_text

    # DB: source query returns "pdf"
    source_result = MagicMock()
    source_result.data = {"source": "pdf"}
    profile_result = MagicMock()
    profile_result.data = {"home_area": "Dublin"}

    db_instance = mock_db.return_value
    db_instance.table.return_value.select.return_value.eq.return_value.single.return_value.execute.side_effect = [
        source_result, profile_result
    ]
    db_instance.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    db_instance.table.return_value.insert.return_value.execute.return_value = MagicMock()

    # extraction_service returns structured data
    mock_extract.return_value = {
        "store_name": "Lidl",
        "purchased_at": "2026-01-15T12:00:00",
        "total_amount": 3.77,
        "items": [],
    }

    await process_receipt_async("r1", MOCK_USER_ID, b"fake-pdf-bytes", "http://img.url")

    mock_pdfplumber.assert_called_once_with(b"fake-pdf-bytes")
    mock_ocr.assert_not_called()  # Gemini OCR should NOT be called
    mock_extract.assert_called_once_with(pdf_text)


@pytest.mark.asyncio
@patch("app.api.v1.receipts.get_service_client")
@patch("app.services.embedding_service.store_item_embedding", new_callable=AsyncMock)
@patch("app.services.price_service.contribute_anonymous_price", new_callable=AsyncMock)
@patch("app.services.extraction_service.extract_receipt_data", new_callable=AsyncMock)
@patch("app.services.ocr_service.extract_text_from_image", new_callable=AsyncMock)
@patch("app.utils.pdf_utils.extract_text_from_pdf")
async def test_pdf_ocr_fallback_for_image_pdf(
    mock_pdfplumber, mock_ocr, mock_extract, mock_price, mock_embed, mock_db
):
    """Image-based PDF with insufficient text falls back to Gemini OCR."""
    # pdfplumber returns very little text (<= 100 chars)
    mock_pdfplumber.return_value = "short"

    ocr_text = "Aldi\n2026-02-10\nApples 2.50\nTotal 2.50"
    mock_ocr.return_value = ocr_text

    # DB: source query returns "pdf"
    source_result = MagicMock()
    source_result.data = {"source": "pdf"}
    profile_result = MagicMock()
    profile_result.data = {"home_area": "Cork"}

    db_instance = mock_db.return_value
    db_instance.table.return_value.select.return_value.eq.return_value.single.return_value.execute.side_effect = [
        source_result, profile_result
    ]
    db_instance.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    db_instance.table.return_value.insert.return_value.execute.return_value = MagicMock()

    mock_extract.return_value = {
        "store_name": "Aldi",
        "purchased_at": "2026-02-10T12:00:00",
        "total_amount": 2.50,
        "items": [],
    }

    await process_receipt_async("r2", MOCK_USER_ID, b"fake-image-pdf", "http://img.url")

    mock_pdfplumber.assert_called_once_with(b"fake-image-pdf")
    mock_ocr.assert_called_once_with(b"fake-image-pdf")  # Gemini OCR SHOULD be called
    mock_extract.assert_called_once_with(ocr_text)
