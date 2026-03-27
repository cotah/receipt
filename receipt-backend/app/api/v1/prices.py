from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from app.utils.auth_utils import get_current_user
from app.utils.text_utils import generate_product_key
from app.database import get_service_client
from app.services.cache_service import get_cache, set_cache
from app.models.price import (
    PriceCompareResponse,
    StorePrice,
    BasketRequest,
    BasketResponse,
    BasketItem,
    SplitRecommendation,
    LeafletOffersResponse,
    LeafletOffer,
)

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/compare", response_model=PriceCompareResponse)
async def compare_prices(
    product: str = Query(...),
    area: str | None = None,
    user_id: str = Depends(get_current_user),
):
    db = get_service_client()
    now = datetime.now(timezone.utc)
    product_key = generate_product_key(product)

    query = (
        db.table("collective_prices")
        .select("*")
        .eq("product_key", product_key)
        .gte("expires_at", now.isoformat())
        .order("unit_price")
    )
    if area:
        query = query.eq("home_area", area)
    result = query.execute()

    # Group by store (keep cheapest per store)
    store_map: dict[str, dict] = {}
    for row in result.data or []:
        s = row["store_name"]
        if s not in store_map or row["unit_price"] < store_map[s]["unit_price"]:
            store_map[s] = row

    stores_sorted = sorted(store_map.values(), key=lambda x: x["unit_price"])
    max_price = stores_sorted[-1]["unit_price"] if stores_sorted else 0

    stores = []
    for i, row in enumerate(stores_sorted):
        stores.append(StorePrice(
            store_name=row["store_name"],
            unit_price=row["unit_price"],
            is_on_offer=row.get("is_on_offer", False),
            last_seen=row["observed_at"],
            confirmations=row.get("confirmation_count", 1),
            is_cheapest=(i == 0),
            saving_vs_most_expensive=round(max_price - row["unit_price"], 2) if i == 0 else None,
        ))

    product_name = stores_sorted[0]["product_name"] if stores_sorted else product
    unit = stores_sorted[0].get("unit") if stores_sorted else None
    last_updated = stores_sorted[0]["observed_at"] if stores_sorted else now.isoformat()

    return PriceCompareResponse(
        product_name=product_name,
        unit=unit,
        last_updated=last_updated,
        stores=stores,
    )


@router.post("/basket", response_model=BasketResponse)
async def calculate_basket(
    body: BasketRequest,
    user_id: str = Depends(get_current_user),
):
    db = get_service_client()
    now = datetime.now(timezone.utc)

    # For each item, find prices at all stores
    all_stores: set[str] = set()
    item_prices: dict[str, dict[str, float]] = {}  # item -> {store: price}

    for item_name in body.items:
        product_key = generate_product_key(item_name)
        result = (
            db.table("collective_prices")
            .select("store_name, unit_price")
            .eq("product_key", product_key)
            .gte("expires_at", now.isoformat())
            .order("unit_price")
            .execute()
        )
        store_prices: dict[str, float] = {}
        for row in result.data or []:
            s = row["store_name"]
            if s not in store_prices:
                store_prices[s] = row["unit_price"]
                all_stores.add(s)
        item_prices[item_name] = store_prices

    total_items = len(body.items)
    summary = []
    for store in sorted(all_stores):
        total = 0.0
        available = 0
        for item_name in body.items:
            price = item_prices.get(item_name, {}).get(store)
            if price is not None:
                total += price
                available += 1
        summary.append(BasketItem(
            store=store,
            total_estimated=round(total, 2),
            items_available=available,
            items_missing=total_items - available,
            savings_vs_most_expensive=0,
        ))

    summary.sort(key=lambda x: x.total_estimated)
    if len(summary) >= 2:
        most_expensive = max(s.total_estimated for s in summary)
        for s in summary:
            s.savings_vs_most_expensive = round(most_expensive - s.total_estimated, 2)

    # Split recommendation: find cheapest store per item
    split_total = 0.0
    split_parts: dict[str, list[str]] = {}
    for item_name in body.items:
        prices = item_prices.get(item_name, {})
        if prices:
            cheapest_store = min(prices, key=prices.get)
            split_total += prices[cheapest_store]
            split_parts.setdefault(cheapest_store, []).append(item_name)

    split_rec = None
    if len(split_parts) > 1 and summary:
        best_single = summary[0].total_estimated
        if split_total < best_single:
            parts_desc = ", ".join(
                f"{', '.join(items)} at {store}" for store, items in split_parts.items()
            )
            split_rec = SplitRecommendation(
                message=f"Buy {parts_desc}",
                total_with_split=round(split_total, 2),
            )

    return BasketResponse(summary=summary, split_recommendation=split_rec)


@router.get("/leaflet-offers", response_model=LeafletOffersResponse)
async def get_leaflet_offers(
    store: str | None = None,
    category: str | None = None,
    page: int = 1,
    limit: int = 100,
    user_id: str = Depends(get_current_user),
):
    cache_key = f"leaflet_offers:{store or 'all'}:{category or 'all'}:{page}"
    cached = get_cache(cache_key)
    if cached is not None:
        return LeafletOffersResponse(**cached)

    db = get_service_client()
    now = datetime.now(timezone.utc)
    offset = (page - 1) * limit

    query = (
        db.table("collective_prices")
        .select("*", count="exact")
        .eq("source", "leaflet")
        .gte("expires_at", now.isoformat())
        .order("unit_price")
        .range(offset, offset + limit - 1)
    )
    if store:
        query = query.eq("store_name", store)
    if category:
        query = query.eq("category", category)
    result = query.execute()

    offers = []
    max_valid = None
    for row in result.data or []:
        valid_until = datetime.fromisoformat(row["expires_at"]).date()
        if max_valid is None or valid_until > max_valid:
            max_valid = valid_until

        offers.append(LeafletOffer(
            store=row["store_name"],
            product_name=row["product_name"],
            unit_price=row["unit_price"],
            original_price=None,
            discount_percent=None,
            category=row["category"],
            valid_from=datetime.fromisoformat(row["observed_at"]).date(),
            valid_until=valid_until,
        ))

    response = LeafletOffersResponse(
        valid_until=max_valid,
        offers=offers,
        total=result.count,
        page=page,
    )
    set_cache(cache_key, response.model_dump(mode="json"), ttl_seconds=3600)
    return response


@router.get("/smart-search")
async def smart_search_products(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=50),
    user_id: str = Depends(get_current_user),
):
    """Smart product search with cross-store grouping.

    Searches all leaflet products and groups the same product
    from different stores together, so the user can compare prices
    at a glance. Results are sorted: multi-store matches first,
    then by cheapest price.
    """
    from app.services.search_service import smart_search

    cache_key = f"smart_search:{q.lower().strip()}:{limit}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    result = await smart_search(q, limit=limit)
    set_cache(cache_key, result, ttl_seconds=1800)  # 30 min cache
    return result


@router.get("/alternatives")
async def get_alternatives(
    product_name: str = Query(
        ..., min_length=2, description="Product to find alternatives for"
    ),
    limit: int = Query(6, ge=1, le=15),
    user_id: str = Depends(get_current_user),
):
    """AI-powered cheaper alternatives for a given product.

    Uses OpenAI to understand the product category and find
    similar/cheaper alternatives from different brands in the database.
    Example: 'Nutella 400g' → suggests store-brand hazelnut spreads.
    """
    from app.services.search_service import find_alternatives

    cache_key = f"alternatives:{product_name.lower().strip()}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    alternatives = await find_alternatives(product_name, limit=limit)
    result = {
        "product_name": product_name,
        "alternatives": alternatives,
        "total": len(alternatives),
    }
    set_cache(cache_key, result, ttl_seconds=3600)  # 1h cache
    return result


@router.get("/price-memory")
async def get_price_memory(
    limit: int = Query(10, ge=1, le=30),
    user_id: str = Depends(get_current_user),
):
    """Price Memory — shows user products they bought that are now cheaper.

    Cross-references receipt_items with current collective_prices to find:
    - Products the user bought recently
    - That are currently available cheaper at any store
    Sorted by biggest potential saving.
    """
    from app.services.search_service import _normalize_for_grouping, _token_similarity

    cache_key = f"price_memory:{user_id}:{limit}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    db = get_service_client()
    now = datetime.now(timezone.utc)

    # Get user's receipt items (last 90 days)
    from datetime import timedelta
    cutoff = (now - timedelta(days=90)).isoformat()

    receipt_items = (
        db.table("receipt_items")
        .select("normalized_name, unit_price, category, receipt_id")
        .eq("user_id", user_id)
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )

    if not receipt_items.data:
        result = {"memories": [], "total": 0, "potential_savings": 0}
        set_cache(cache_key, result, ttl_seconds=3600)
        return result

    # Get the store_name for each receipt
    receipt_ids = list({r["receipt_id"] for r in receipt_items.data})
    receipts = (
        db.table("receipts")
        .select("id, store_name, purchased_at")
        .in_("id", receipt_ids)
        .execute()
    )
    receipt_map = {r["id"]: r for r in (receipts.data or [])}

    # For each user product, find current offers
    memories = []
    seen_products: set[str] = set()

    for item in receipt_items.data:
        name = item["normalized_name"]
        if not name or name.lower() in seen_products:
            continue

        receipt_info = receipt_map.get(item["receipt_id"], {})
        paid_price = float(item["unit_price"])
        paid_store = receipt_info.get("store_name", "Unknown")
        paid_date = receipt_info.get("purchased_at", "")

        # Search for this product in current offers
        words = name.lower().split()[:3]
        pattern = "%" + "%".join(words) + "%"

        try:
            matches = (
                db.table("collective_prices")
                .select("product_name, store_name, unit_price, is_on_offer")
                .eq("source", "leaflet")
                .gte("expires_at", now.isoformat())
                .ilike("product_name", pattern)
                .order("unit_price")
                .limit(5)
                .execute()
            )

            for m in matches.data or []:
                current_price = float(m["unit_price"])
                # Use token similarity to confirm it's the same product
                norm_user = _normalize_for_grouping(name)
                norm_match = _normalize_for_grouping(m["product_name"])
                if _token_similarity(norm_user, norm_match) < 0.4:
                    continue

                saving = round(paid_price - current_price, 2)
                if saving > 0.10:  # At least 10c saving
                    memories.append({
                        "product_name": name,
                        "paid_price": paid_price,
                        "paid_store": paid_store,
                        "paid_date": paid_date[:10] if paid_date else None,
                        "current_price": current_price,
                        "current_store": m["store_name"],
                        "is_on_offer": m.get("is_on_offer", False),
                        "saving": saving,
                        "saving_pct": round(saving / paid_price * 100),
                        "message": (
                            f"You paid €{paid_price:.2f} at {paid_store}"
                            f" — now €{current_price:.2f} at {m['store_name']}"
                            f" (save €{saving:.2f})"
                        ),
                    })
                    seen_products.add(name.lower())
                    break  # One match per user product
        except Exception:
            pass

    # Sort by saving descending
    memories.sort(key=lambda x: -x["saving"])
    memories = memories[:limit]
    total_savings = round(sum(m["saving"] for m in memories), 2)

    result = {
        "memories": memories,
        "total": len(memories),
        "potential_savings": total_savings,
    }
    set_cache(cache_key, result, ttl_seconds=1800)  # 30 min cache
    return result


@router.get("/savings-summary")
async def get_savings_summary(
    user_id: str = Depends(get_current_user),
):
    """Savings summary for the home screen.

    Calculates:
    - Total potential savings this month (from price-memory matches)
    - Number of products with better prices available
    - Best single saving opportunity
    """
    cache_key = f"savings_summary:{user_id}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    db = get_service_client()
    now = datetime.now(timezone.utc)

    from datetime import timedelta
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Get this month's receipt items with store info
    receipt_items = (
        db.table("receipt_items")
        .select("normalized_name, unit_price, receipt_id")
        .eq("user_id", user_id)
        .gte("created_at", month_start.isoformat())
        .execute()
    )

    if not receipt_items.data:
        result = {
            "month_potential_savings": 0,
            "products_with_better_price": 0,
            "best_saving": None,
            "receipt_count": 0,
        }
        set_cache(cache_key, result, ttl_seconds=3600)
        return result

    receipt_ids = list({r["receipt_id"] for r in receipt_items.data})
    receipts = (
        db.table("receipts")
        .select("id, store_name")
        .in_("id", receipt_ids)
        .execute()
    )
    receipt_map = {r["id"]: r["store_name"] for r in (receipts.data or [])}

    total_savings = 0.0
    better_count = 0
    best_saving = None
    seen: set[str] = set()

    for item in receipt_items.data:
        name = item["normalized_name"]
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())

        paid = float(item["unit_price"])
        paid_store = receipt_map.get(item["receipt_id"], "")

        words = name.lower().split()[:3]
        pattern = "%" + "%".join(words) + "%"

        try:
            matches = (
                db.table("collective_prices")
                .select("product_name, store_name, unit_price")
                .eq("source", "leaflet")
                .gte("expires_at", now.isoformat())
                .ilike("product_name", pattern)
                .order("unit_price")
                .limit(1)
                .execute()
            )
            if matches.data:
                current = float(matches.data[0]["unit_price"])
                saving = paid - current
                if saving > 0.05:
                    total_savings += saving
                    better_count += 1
                    if best_saving is None or saving > best_saving["saving"]:
                        best_saving = {
                            "product": name,
                            "paid": paid,
                            "paid_store": paid_store,
                            "now": current,
                            "now_store": matches.data[0]["store_name"],
                            "saving": round(saving, 2),
                        }
        except Exception:
            pass

    result = {
        "month_potential_savings": round(total_savings, 2),
        "products_with_better_price": better_count,
        "best_saving": best_saving,
        "receipt_count": len(receipt_ids),
    }
    set_cache(cache_key, result, ttl_seconds=1800)
    return result
