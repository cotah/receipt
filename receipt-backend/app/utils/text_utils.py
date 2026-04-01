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
    """Generate a normalized, order-independent key like 'breast_chicken_fillet'.

    Words are sorted alphabetically so 'Tesco Chicken Fillet' and
    'Chicken Fillet Tesco' produce the same key.
    Store names are stripped to avoid false mismatches.
    """
    key = name.lower().strip()
    key = unicodedata.normalize("NFKD", key).encode("ascii", "ignore").decode()

    # Strip common store names — they appear inconsistently on receipts vs leaflets
    store_names = {"tesco", "lidl", "aldi", "dunnes", "stores", "supervalu", "super", "valu"}
    words = re.sub(r"[^a-z0-9]+", " ", key).split()
    words = [w for w in words if w and w not in store_names]

    # Normalise size suffixes: "1lt" → "1l", "500gm" → "500g"
    normalised = []
    for w in words:
        w = re.sub(r"(\d+)lt\b", r"\1l", w)
        w = re.sub(r"(\d+)gm\b", r"\1g", w)
        w = re.sub(r"(\d+)ml\b", r"\1ml", w)
        normalised.append(w)

    # Sort alphabetically — order-independent
    normalised.sort()

    key = "_".join(normalised)
    if unit:
        key = f"{key}_{unit.lower().strip()}"
    return key
