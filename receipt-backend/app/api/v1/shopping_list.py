"""Shopping list endpoints — add from deals, manage, group by store."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import get_service_client
from app.utils.auth_utils import get_current_user
from app.utils.text_utils import generate_product_key

log = logging.getLogger(__name__)
router = APIRouter(prefix="/shopping-list", tags=["shopping-list"])


class AddItemRequest(BaseModel):
    product_name: str
    store_name: str | None = None
    unit_price: float | None = None
    category: str = "Other"
    source: str = "manual"  # "manual", "deal", "memory"


class CheckItemRequest(BaseModel):
    item_id: str
    is_checked: bool = True


@router.get("")
async def get_shopping_list(
    user_id: str = Depends(get_current_user),
):
    """Get user's shopping list, grouped by store.

    Returns:
    - items grouped by store_name (null store = "Any Store")
    - total estimated cost per store
    - overall total
    - checked/unchecked counts
    """
    db = get_service_client()

    items = (
        db.table("shopping_list_items")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_checked", False)
        .order("store_name")
        .order("category")
        .order("added_at")
        .execute()
    )

    # Group by store
    by_store: dict[str, list] = {}
    for item in items.data or []:
        store = item.get("store_name") or "Any Store"
        if store not in by_store:
            by_store[store] = []
        by_store[store].append(item)

    # Calculate totals
    stores = []
    overall_total = 0.0
    for store, store_items in sorted(by_store.items()):
        store_total = sum(
            float(i.get("unit_price") or 0) for i in store_items
        )
        overall_total += store_total
        stores.append({
            "store_name": store,
            "items": store_items,
            "item_count": len(store_items),
            "estimated_total": round(store_total, 2),
        })

    # Checked items count
    checked = (
        db.table("shopping_list_items")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("is_checked", True)
        .execute()
    )

    return {
        "stores": stores,
        "total_items": sum(len(s["items"]) for s in stores),
        "estimated_total": round(overall_total, 2),
        "checked_count": checked.count or 0,
    }


@router.post("/add")
async def add_item(
    body: AddItemRequest,
    user_id: str = Depends(get_current_user),
):
    """Add an item to the shopping list (from deal, memory, or manual)."""
    db = get_service_client()

    product_key = generate_product_key(body.product_name)

    # Check for duplicate (same product + store, not checked)
    existing = (
        db.table("shopping_list_items")
        .select("id")
        .eq("user_id", user_id)
        .eq("product_key", product_key)
        .eq("is_checked", False)
        .limit(1)
        .execute()
    )
    if existing.data:
        return {"status": "exists", "message": "Already in your list"}

    result = (
        db.table("shopping_list_items")
        .insert({
            "user_id": user_id,
            "product_name": body.product_name,
            "product_key": product_key,
            "store_name": body.store_name,
            "unit_price": body.unit_price,
            "category": body.category,
            "source": body.source,
        })
        .execute()
    )

    return {
        "status": "added",
        "item": result.data[0] if result.data else None,
    }


@router.post("/check")
async def check_item(
    body: CheckItemRequest,
    user_id: str = Depends(get_current_user),
):
    """Mark an item as checked (bought) or uncheck it."""
    db = get_service_client()

    update = {"is_checked": body.is_checked}
    if body.is_checked:
        update["checked_at"] = datetime.now(timezone.utc).isoformat()

    result = (
        db.table("shopping_list_items")
        .update(update)
        .eq("id", body.item_id)
        .eq("user_id", user_id)
        .execute()
    )

    return {"status": "updated", "item": result.data[0] if result.data else None}


@router.delete("/{item_id}")
async def remove_item(
    item_id: str,
    user_id: str = Depends(get_current_user),
):
    """Remove an item from the list."""
    db = get_service_client()

    db.table("shopping_list_items").delete().eq(
        "id", item_id
    ).eq("user_id", user_id).execute()

    return {"status": "deleted"}


@router.post("/clear-checked")
async def clear_checked(
    user_id: str = Depends(get_current_user),
):
    """Remove all checked items."""
    db = get_service_client()

    db.table("shopping_list_items").delete().eq(
        "user_id", user_id
    ).eq("is_checked", True).execute()

    return {"status": "cleared"}
