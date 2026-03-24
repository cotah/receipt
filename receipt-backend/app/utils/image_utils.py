import io
import base64
from PIL import Image


def compress_image(image_bytes: bytes, max_size_mb: float = 2.0) -> bytes:
    """Compress image to stay under max_size_mb."""
    max_bytes = int(max_size_mb * 1024 * 1024)
    if len(image_bytes) <= max_bytes:
        return image_bytes

    img = Image.open(io.BytesIO(image_bytes))
    if img.mode == "RGBA":
        img = img.convert("RGB")

    quality = 85
    while quality >= 20:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        result = buffer.getvalue()
        if len(result) <= max_bytes:
            return result
        quality -= 10

    # Last resort: resize
    img.thumbnail((1600, 2400), Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=60, optimize=True)
    return buffer.getvalue()


def validate_image(content_type: str, size: int, max_size_mb: int = 10) -> str | None:
    """Return error message if invalid, None if OK."""
    allowed = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
    if content_type not in allowed:
        return f"Invalid file type: {content_type}. Allowed: jpg, png, webp, pdf"
    max_bytes = max_size_mb * 1024 * 1024
    if size > max_bytes:
        return f"File too large: {size / 1024 / 1024:.1f}MB. Max: {max_size_mb}MB"
    return None


def to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")
