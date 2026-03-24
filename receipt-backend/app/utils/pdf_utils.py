import io
import logging

import pdfplumber

log = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text directly from a PDF using pdfplumber.

    Returns the extracted text or an empty string if the PDF is
    image-based or an error occurs.
    """
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            return "\n".join(pages_text)
    except Exception as e:
        log.debug(f"pdfplumber extraction failed: {e}")
        return ""


def is_text_pdf(pdf_bytes: bytes) -> bool:
    """Return True if the PDF contains enough extractable text (>100 chars)."""
    return len(extract_text_from_pdf(pdf_bytes)) > 100
