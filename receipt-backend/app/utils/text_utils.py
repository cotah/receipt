import re
import unicodedata


def normalize_product_name(raw_name: str) -> str:
    """Clean up raw receipt product name."""
    name = raw_name.strip()
    # Remove common receipt artifacts
    name = re.sub(r"\b(LH|LS|PM|EA|KG|LT|PK)\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\b\d+\s*[xX]\s*\d+\s*(ml|g|kg|l)\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip()
    # Title case
    name = name.title()
    return name


def generate_product_key(name: str, unit: str | None = None) -> str:
    """Generate a normalized key like 'banana_kg'."""
    key = name.lower().strip()
    key = unicodedata.normalize("NFKD", key).encode("ascii", "ignore").decode()
    key = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    if unit:
        key = f"{key}_{unit.lower().strip()}"
    return key
