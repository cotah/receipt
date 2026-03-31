"""Shopping list endpoints — add from deals, manage, group by store."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
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

    Includes items from shared partner (if linked via list_shared_with).

    Returns:
    - items grouped by store_name (null store = "Any Store")
    - total estimated cost per store
    - overall total
    - checked/unchecked counts
    - shared_with: partner name (if sharing)
    """
    db = get_service_client()

    # Check if user has a shared partner
    user_ids = [user_id]
    shared_with_name = None
    try:
        profile = (
            db.table("profiles")
            .select("list_shared_with")
            .eq("id", user_id)
            .single()
            .execute()
        )
        partner_id = (profile.data or {}).get("list_shared_with")
        if partner_id:
            user_ids.append(partner_id)
            # Get partner's name
            partner = (
                db.table("profiles")
                .select("full_name")
                .eq("id", partner_id)
                .single()
                .execute()
            )
            shared_with_name = (partner.data or {}).get("full_name", "Partner")
    except Exception:
        pass

    # Get items from both users
    items = (
        db.table("shopping_list_items")
        .select("*")
        .in_("user_id", user_ids)
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
        "shared_with": shared_with_name,
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


@router.get("/optimize")
async def optimize_shopping_list(
    user_id: str = Depends(get_current_user),
):
    """Smart Split — find cheapest way to buy your shopping list.

    Returns two strategies:
    1. single_store: Cheapest total at ONE store (convenience)
    2. multi_store: Cheapest per item across ALL stores (maximum savings)

    Also includes per-item price comparisons.
    """
    db = get_service_client()
    now = datetime.now(timezone.utc)

    # Get unchecked items
    items = (
        db.table("shopping_list_items")
        .select("id, product_name, product_key, unit_price, category, store_name")
        .eq("user_id", user_id)
        .eq("is_checked", False)
        .execute()
    )
    item_list = items.data or []
    if not item_list:
        return {
            "status": "empty",
            "message": "Your shopping list is empty",
            "single_store": None,
            "multi_store": None,
            "items": [],
        }

    # For each item, find prices across all stores
    item_prices = []
    all_stores: set[str] = set()

    for item in item_list:
        product_key = item["product_key"]
        name = item["product_name"]

        # Search for this product in collective_prices via RPC
        try:
            result = db.rpc(
                "search_products",
                {"p_query": f"%{product_key}%", "p_limit": 10},
            ).execute()
            # Filter exact matches
            matches = [r for r in (result.data or []) if r.get("product_key") == product_key]

            # Fallback to name search
            if not matches:
                words = [w for w in name.lower().split() if len(w) > 2][:3]
                if words:
                    pattern = "%" + "%".join(words) + "%"
                    result = db.rpc(
                        "search_products",
                        {"p_query": pattern, "p_limit": 10},
                    ).execute()
                    matches = result.data or []
        except Exception as e:
            log.warning("optimize: search failed for '%s': %s", name, e)
            matches = []

        # Build store→price map for this item
        store_prices: dict[str, dict] = {}
        for m in matches:
            store = m["store_name"]
            price = float(m["unit_price"])
            if store not in store_prices or price < store_prices[store]["price"]:
                store_prices[store] = {
                    "price": price,
                    "product_name": m["product_name"],
                }
            all_stores.add(store)

        cheapest = min(store_prices.items(), key=lambda x: x[1]["price"]) if store_prices else None

        item_prices.append({
            "item_id": item["id"],
            "product_name": name,
            "list_price": float(item.get("unit_price") or 0),
            "store_prices": {s: v["price"] for s, v in store_prices.items()},
            "cheapest_store": cheapest[0] if cheapest else None,
            "cheapest_price": cheapest[1]["price"] if cheapest else None,
        })

    # Strategy 1: Best SINGLE store
    store_totals: dict[str, dict] = {}
    for store in all_stores:
        total = 0.0
        found = 0
        missing = 0
        for ip in item_prices:
            if store in ip["store_prices"]:
                total += ip["store_prices"][store]
                found += 1
            else:
                missing += 1
        store_totals[store] = {
            "store": store,
            "total": round(total, 2),
            "items_found": found,
            "items_missing": missing,
        }

    # Sort by total (but prioritize stores with more items found)
    sorted_stores = sorted(
        store_totals.values(),
        key=lambda s: (-s["items_found"], s["total"]),
    )
    best_single = sorted_stores[0] if sorted_stores else None

    # Strategy 2: Multi-store (cheapest per item)
    multi_store_items = []
    multi_total = 0.0
    stores_needed: set[str] = set()
    for ip in item_prices:
        if ip["cheapest_store"]:
            multi_store_items.append({
                "product_name": ip["product_name"],
                "store": ip["cheapest_store"],
                "price": ip["cheapest_price"],
            })
            multi_total += ip["cheapest_price"]
            stores_needed.add(ip["cheapest_store"])
        else:
            multi_store_items.append({
                "product_name": ip["product_name"],
                "store": None,
                "price": ip["list_price"],
            })
            multi_total += ip["list_price"]

    # Calculate savings
    single_total = best_single["total"] if best_single else 0
    savings_vs_single = round(single_total - multi_total, 2) if single_total > 0 else 0

    return {
        "status": "ok",
        "item_count": len(item_prices),
        "single_store": {
            "recommendation": best_single["store"] if best_single else None,
            "total": best_single["total"] if best_single else 0,
            "items_found": best_single["items_found"] if best_single else 0,
            "items_missing": best_single["items_missing"] if best_single else 0,
            "all_stores": sorted_stores,
        },
        "multi_store": {
            "total": round(multi_total, 2),
            "stores_needed": len(stores_needed),
            "store_list": sorted(stores_needed),
            "items": multi_store_items,
            "savings_vs_single": max(savings_vs_single, 0),
        },
        "items": item_prices,
    }


# ─── Sharing endpoints ───

@router.post("/share")
async def share_list(user_id: str = Depends(get_current_user)):
    """Generate a share code for the user's shopping list."""
    import secrets
    db = get_service_client()

    # Check if user already has a share code
    profile = (
        db.table("profiles")
        .select("list_share_code, full_name")
        .eq("id", user_id)
        .single()
        .execute()
    )

    existing_code = (profile.data or {}).get("list_share_code")
    if existing_code:
        return {"share_code": existing_code}

    # Generate unique 6-char code
    code = secrets.token_hex(3).upper()  # e.g. "A1B2C3"
    db.table("profiles").update({"list_share_code": code}).eq("id", user_id).execute()

    return {"share_code": code}


@router.post("/join")
async def join_shared_list(
    code: str = Query(..., min_length=4),
    user_id: str = Depends(get_current_user),
):
    """Join someone's shared shopping list using their code."""
    db = get_service_client()

    # Find the owner of this code
    owner = (
        db.table("profiles")
        .select("id, full_name")
        .eq("list_share_code", code.upper().strip())
        .single()
        .execute()
    )

    if not owner.data:
        raise HTTPException(status_code=404, detail="Invalid share code")

    owner_id = owner.data["id"]
    if owner_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot join your own list")

    # Link both users
    db.table("profiles").update({"list_shared_with": owner_id}).eq("id", user_id).execute()
    db.table("profiles").update({"list_shared_with": user_id}).eq("id", owner_id).execute()

    return {
        "status": "ok",
        "shared_with": owner.data.get("full_name", "Partner"),
    }


@router.delete("/unlink")
async def unlink_shared_list(user_id: str = Depends(get_current_user)):
    """Stop sharing shopping list with partner."""
    db = get_service_client()

    # Get current partner
    profile = (
        db.table("profiles")
        .select("list_shared_with")
        .eq("id", user_id)
        .single()
        .execute()
    )
    partner_id = (profile.data or {}).get("list_shared_with")

    # Unlink both sides
    db.table("profiles").update({"list_shared_with": None}).eq("id", user_id).execute()
    if partner_id:
        db.table("profiles").update({"list_shared_with": None}).eq("id", partner_id).execute()

    return {"status": "ok"}


@router.get("/share-status")
async def share_status(user_id: str = Depends(get_current_user)):
    """Check sharing status — who you're sharing with."""
    db = get_service_client()

    profile = (
        db.table("profiles")
        .select("list_share_code, list_shared_with")
        .eq("id", user_id)
        .single()
        .execute()
    )

    data = profile.data or {}
    partner_id = data.get("list_shared_with")
    partner_name = None

    if partner_id:
        partner = (
            db.table("profiles")
            .select("full_name")
            .eq("id", partner_id)
            .single()
            .execute()
        )
        partner_name = (partner.data or {}).get("full_name", "Partner")

    return {
        "share_code": data.get("list_share_code"),
        "is_sharing": partner_id is not None,
        "partner_name": partner_name,
    }
