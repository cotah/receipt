from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from app.utils.auth_utils import get_current_user
from app.utils.text_utils import generate_product_key
from app.database import get_service_client
from app.config import settings
from app.services.cache_service import get_cache, set_cache
from app.services.search_service import are_comparable_products, _normalize_for_grouping, _token_similarity, _per_unit_price
from app.models.price import (
    PriceCompareResponse,
    StorePrice,
    BasketRequest,
    BasketResponse,
    BasketItem,
    BasketItemDetail,
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

    # Try exact product_key match first via RPC (avoids vector column crash)
    try:
        result = db.rpc(
            "search_products",
            {"p_query": f"%{product_key}%", "p_limit": 30},
        ).execute()
        # Filter to exact product_key matches
        exact = [r for r in (result.data or []) if r.get("product_key") == product_key]
        if exact:
            result.data = exact
    except Exception:
        result = type('R', (), {'data': []})()

    # Fallback: ILIKE search if exact key returns nothing
    if not result.data:
        words = product.lower().split()[:4]
        pattern = "%" + "%".join(words) + "%"
        try:
            result = db.rpc(
                "search_products",
                {"p_query": pattern, "p_limit": 20},
            ).execute()
        except Exception:
            result = type('R', (), {'data': []})()

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

    # Normalize store names
    _STORE_NORMALIZE = {
        "tesco": "Tesco", "lidl": "Lidl", "aldi": "Aldi",
        "supervalu": "SuperValu", "dunnes": "Dunnes",
        "dunnes stores": "Dunnes",
    }

    for item_name in body.items:
        product_key = generate_product_key(item_name)
        result = (
            db.table("collective_prices")
            .select("store_name, unit_price, product_name")
            .eq("product_key", product_key)
            .gte("expires_at", now.isoformat())
            .order("unit_price")
            .execute()
        )
        # ILIKE fallback if exact key fails
        if not result.data:
            words = [w for w in item_name.lower().split() if len(w) > 2][:4]
            if words:
                pattern = "%" + "%".join(words) + "%"
                try:
                    result = db.rpc(
                        "search_products",
                        {"p_query": pattern, "p_limit": 20},
                    ).execute()
                except Exception:
                    pass
        store_prices: dict[str, float] = {}
        for row in result.data or []:
            raw_store = row["store_name"]
            s = _STORE_NORMALIZE.get(raw_store.lower().strip(), raw_store)
            if s not in store_prices:
                store_prices[s] = float(row["unit_price"])
                all_stores.add(s)
        item_prices[item_name] = store_prices

    total_items = len(body.items)
    summary = []
    for store in sorted(all_stores):
        total = 0.0
        available = 0
        item_details = []
        for item_name in body.items:
            price = item_prices.get(item_name, {}).get(store)
            if price is not None:
                total += price
                available += 1
                item_details.append(BasketItemDetail(name=item_name, price=round(price, 2), found=True))
            else:
                item_details.append(BasketItemDetail(name=item_name, price=None, found=False))
        summary.append(BasketItem(
            store=store,
            total_estimated=round(total, 2),
            items_available=available,
            items_missing=total_items - available,
            savings_vs_most_expensive=0,
            items=item_details,
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
            cheapest_store = min(prices, key=prices.get)  # type: ignore
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
    set_cache(cache_key, response.model_dump(mode="json"), ttl_seconds=600)
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
    set_cache(cache_key, result, ttl_seconds=600)  # 30 min cache
    return result


@router.get("/alternatives")
async def get_alternatives(
    product_name: str = Query(
        ..., min_length=2, description="Product to find alternatives for"
    ),
    exclude_key: str | None = Query(None, description="Product key to exclude from results"),
    limit: int = Query(6, ge=1, le=15),
    user_id: str = Depends(get_current_user),
):
    """Same product at different stores/sizes.

    Uses AI to find the EXACT same product type from different stores,
    excluding the product already being viewed.
    """
    from app.services.search_service import find_alternatives

    cache_key = f"alternatives:{product_name.lower().strip()}:{exclude_key or ''}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    exclude_keys = [exclude_key] if exclude_key else None
    alternatives = await find_alternatives(product_name, limit=limit, exclude_keys=exclude_keys)
    result = {
        "product_name": product_name,
        "alternatives": alternatives,
        "total": len(alternatives),
    }
    set_cache(cache_key, result, ttl_seconds=600)
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
        set_cache(cache_key, result, ttl_seconds=600)
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

    # For each user product, find current offers with STRICT matching
    memories = []
    seen_products: set[str] = set()

    # Collect candidates first, then AI-verify the best ones
    candidates: list[dict] = []

    for item in receipt_items.data:
        name = item["normalized_name"]
        if not name or name.lower() in seen_products:
            continue
        if len(name) < 3 or name.lower() in {"deposit", "bag", "carrier bag", "bags"}:
            continue

        receipt_info = receipt_map.get(item["receipt_id"], {})
        paid_price = float(item["unit_price"])
        paid_store = receipt_info.get("store_name", "Unknown")
        paid_date = receipt_info.get("purchased_at", "")
        item_category = item.get("category", "Other")

        words = [w for w in name.lower().split() if len(w) > 2][:5]
        if not words:
            continue
        pattern = "%" + "%".join(words) + "%"

        try:
            matches = db.rpc(
                "search_products",
                {"p_query": pattern, "p_source": "leaflet", "p_limit": 10},
            ).execute()

            for m in matches.data or []:
                current_price = float(m["unit_price"])

                # Strict product matching: same product, similar size, comparable price
                if not are_comparable_products(name, m["product_name"], paid_price, current_price):
                    continue

                candidates.append({
                    "user_product": name,
                    "user_price": paid_price,
                    "user_store": paid_store,
                    "user_date": paid_date[:10] if paid_date else None,
                    "user_category": item_category,
                    "match_name": m["product_name"],
                    "match_price": current_price,
                    "match_store": m["store_name"],
                    "match_category": m.get("category", "Other"),
                    "is_on_offer": m.get("is_on_offer", False),
                    "similarity": similarity,
                })
                seen_products.add(name.lower())
                break  # One candidate per user product
        except Exception:
            pass

    # AI VERIFICATION — ask GPT to confirm matches are the same product
    # One API call for all candidates (cheap: ~200 tokens)
    if candidates:
        verified = await _ai_verify_price_matches(candidates)
    else:
        verified = []

    verified_keys = {(v["user_product"], v["match_name"]) for v in verified}

    # LAYER 5 — Store uncertain candidates for user confirmation
    # (candidates that passed rules but AI didn't verify or AI failed)
    uncertain = [
        c for c in candidates
        if (c["user_product"], c["match_name"]) not in verified_keys
    ]
    if uncertain:
        for uc in uncertain:
            try:
                # Check if already asked
                existing = (
                    db.table("price_match_confirmations")
                    .select("id")
                    .eq("user_id", user_id)
                    .eq("receipt_item_name", uc["user_product"])
                    .eq("matched_product_name", uc["match_name"])
                    .limit(1)
                    .execute()
                )
                if not existing.data:
                    db.table("price_match_confirmations").insert({
                        "user_id": user_id,
                        "receipt_item_name": uc["user_product"],
                        "receipt_item_price": uc["user_price"],
                        "receipt_store": uc["user_store"],
                        "matched_product_name": uc["match_name"],
                        "matched_product_price": uc["match_price"],
                        "matched_store": uc["match_store"],
                    }).execute()
            except Exception:
                pass

    # Include previously user-confirmed matches too
    try:
        confirmed_matches = (
            db.table("price_match_confirmations")
            .select("receipt_item_name, receipt_item_price, receipt_store, matched_product_name, matched_product_price, matched_store")
            .eq("user_id", user_id)
            .eq("confirmed", True)
            .execute()
        )
        for cm in confirmed_matches.data or []:
            # Check if this match is still valid (product still in offers)
            current_check = (
                db.table("collective_prices")
                .select("unit_price")
                .eq("product_name", cm["matched_product_name"])
                .eq("store_name", cm["matched_store"])
                .gte("expires_at", now.isoformat())
                .limit(1)
                .execute()
            )
            if current_check.data:
                current_price = float(current_check.data[0]["unit_price"])
                paid_price = float(cm["receipt_item_price"])
                saving = round(paid_price - current_price, 2)
                if saving > 0.10:
                    verified.append({
                        "user_product": cm["receipt_item_name"],
                        "user_price": paid_price,
                        "user_store": cm["receipt_store"],
                        "match_price": current_price,
                        "match_store": cm["matched_store"],
                        "is_on_offer": False,
                    })
    except Exception:
        pass

    for v in verified:
        saving = round(v["user_price"] - v["match_price"], 2)
        if saving > 0.10:
            memories.append({
                "product_name": v["user_product"],
                "paid_price": v["user_price"],
                "paid_store": v["user_store"],
                "paid_date": v.get("user_date"),
                "current_price": v["match_price"],
                "current_store": v["match_store"],
                "is_on_offer": v.get("is_on_offer", False),
                "saving": saving,
                "saving_pct": round(saving / v["user_price"] * 100),
                "message": (
                    f"You paid €{v['user_price']:.2f} at {v['user_store']}"
                    f" — now €{v['match_price']:.2f} at {v['match_store']}"
                    f" (save €{saving:.2f})"
                ),
            })

    # Sort by saving descending
    memories.sort(key=lambda x: -x["saving"])
    memories = memories[:limit]
    total_savings = round(sum(m["saving"] for m in memories), 2)

    result = {
        "memories": memories,
        "total": len(memories),
        "potential_savings": total_savings,
    }
    set_cache(cache_key, result, ttl_seconds=600)  # 30 min cache
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
        set_cache(cache_key, result, ttl_seconds=600)
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

    from app.services.search_service import _normalize_for_grouping, _token_similarity

    for item in receipt_items.data:
        name = item["normalized_name"]
        if not name or name.lower() in seen:
            continue
        if len(name) < 3 or name.lower() in {"deposit", "bag", "carrier bag", "bags"}:
            continue
        seen.add(name.lower())

        paid = float(item["unit_price"])
        paid_store = receipt_map.get(item["receipt_id"], "")

        words = [w for w in name.lower().split() if len(w) > 2][:5]
        if not words:
            continue
        pattern = "%" + "%".join(words) + "%"

        try:
            matches = db.rpc(
                "search_products",
                {"p_query": pattern, "p_source": "leaflet", "p_limit": 5},
            ).execute()
            for m in (matches.data or []):
                current = float(m["unit_price"])
                # Strict matching: same product, similar size
                if not are_comparable_products(name, m["product_name"], paid, current):
                    continue

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
                            "now_store": m["store_name"],
                            "saving": round(saving, 2),
                        }
                    break  # One match per product
        except Exception:
            pass

    # Get REAL attributed savings (only from confirmed purchases via SmartDocket alerts)
    try:
        attr_result = (
            db.table("savings_attributions")
            .select("saving")
            .eq("user_id", user_id)
            .gte("created_at", month_start.isoformat())
            .execute()
        )
        attributed = sum(float(a.get("saving", 0)) for a in (attr_result.data or []))
    except Exception:
        attributed = 0.0

    result = {
        "month_potential_savings": round(total_savings, 2),
        "products_with_better_price": better_count,
        "best_saving": best_saving,
        "receipt_count": len(receipt_ids),
        "attributed_savings": round(attributed, 2),
    }
    set_cache(cache_key, result, ttl_seconds=600)  # 10 min cache
    return result


async def _ai_verify_price_matches(candidates: list[dict]) -> list[dict]:
    """Use GPT to verify that product matches are truly the EXACT SAME product.

    CRITICAL: This is the brain that ensures precision. A wrong match
    destroys user trust.

    Rules:
    - SAME product type, SAME cut, SAME form = YES
    - Different brand = YES (Tesco Chicken Breast vs Aldi Chicken Breast)
    - Different size = YES but flag it (500g vs 1kg)
    - Different cut = NO (breast vs thigh)
    - Different product = NO (apple juice vs orange juice)
    - Different form = NO (chicken burger vs chicken fillet)
    """
    if not candidates:
        return []

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # Build verification prompt
    pairs = []
    for i, c in enumerate(candidates):
        pairs.append(
            f"{i+1}. \"{c['user_product']}\" (€{c['user_price']:.2f}) "
            f"vs \"{c['match_name']}\" (€{c['match_price']:.2f})"
        )

    prompt = f"""You are verifying if grocery product pairs are the EXACT SAME product type.

ULTRA-STRICT RULES — read carefully:

1. SAME product = YES:
   - "Chicken Breast Fillets 500g" vs "Irish Chicken Breast Fillets 1kg" = YES (same cut, different size)
   - "Apple Juice 1L" vs "Pressed Apple Juice 500ml" = YES (same juice, different size)
   - "Tesco Semi-Skimmed Milk 2L" vs "Avonmore Milk Low Fat 2L" = YES (same product, different brand)
   - "Cheddar Cheese 200g" vs "Mature Cheddar 400g" = YES (same cheese type)

2. DIFFERENT product = NO:
   - "Chicken Breast" vs "Chicken Thighs" = NO (different cut!)
   - "Chicken Breast" vs "Chicken Burger" = NO (different form!)
   - "Chicken Breast" vs "Turkey Breast" = NO (different meat!)
   - "Apple Juice" vs "Orange Juice" = NO (different fruit!)
   - "Apple Juice" vs "Pineapple Juice" = NO (different fruit!)
   - "Milk" vs "Oat Milk" = NO (different product!)
   - "Butter" vs "Peanut Butter" = NO
   - "Bread" vs "Garlic Bread" = NO
   - "Onion Rings" vs "Red Onions" = NO (snack vs vegetable!)
   - "Egg" vs "Easter Egg" = NO (food vs chocolate!)
   - "Rice" vs "Rice Cakes" = NO
   - "Cream" vs "Ice Cream" = NO

3. If products are the same type but VERY different price AND no size difference visible, say NO.

For each pair respond ONLY with the number and YES or NO. Nothing else:
1. YES
2. NO

Pairs:
{chr(10).join(pairs)}"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4.1-nano",
            temperature=0,
            max_completion_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response.choices[0].message.content.strip()

        # Parse YES/NO responses
        verified = []
        for line in answer.split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split(".", 1)
            if len(parts) == 2:
                try:
                    idx = int(parts[0].strip()) - 1
                    is_yes = "YES" in parts[1].upper()
                    if is_yes and 0 <= idx < len(candidates):
                        verified.append(candidates[idx])
                except (ValueError, IndexError):
                    pass

        import logging
        logging.getLogger(__name__).info(
            "AI verify: %d/%d candidates confirmed as same product",
            len(verified), len(candidates),
        )
        return verified

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"AI verify failed: {e}")
        return []


@router.get("/smart-timing")
async def get_smart_timing(
    product_name: str | None = Query(None, description="Product to check timing for"),
    user_id: str = Depends(get_current_user),
):
    """Smart Timing — predict when products go on sale.

    With enough history (4+ weeks): detects price cycles and predicts
    next sale date for specific products.

    Always available: shows store refresh schedule and when current
    offers expire, so users know the best time to shop.
    """
    from datetime import timedelta

    cache_key = f"smart_timing:{user_id}:{product_name or 'general'}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    db = get_service_client()
    now = datetime.now(timezone.utc)

    # Store schedule info (always available)
    store_schedules = [
        {
            "store": "SuperValu",
            "refresh_day": "Every 2 days",
            "refresh_detail": "Prices updated every 2 days",
            "next_refresh": _next_odd_day(now).isoformat(),
        },
        {
            "store": "Tesco",
            "refresh_day": "Every 2 days",
            "refresh_detail": "Prices updated every 2 days",
            "next_refresh": _next_even_day(now).isoformat(),
        },
        {
            "store": "Lidl",
            "refresh_day": "Thursday",
            "refresh_detail": "New offers every Thursday",
            "next_refresh": _next_weekday(now, 3).isoformat(),  # Thursday=3
        },
        {
            "store": "Aldi",
            "refresh_day": "Thursday",
            "refresh_detail": "New offers every Thursday",
            "next_refresh": _next_weekday(now, 3).isoformat(),
        },
    ]

    # Current offers expiry info
    expiry_data = (
        db.table("collective_prices")
        .select("store_name, expires_at")
        .eq("source", "leaflet")
        .gte("expires_at", now.isoformat())
        .execute()
    )
    store_expiry: dict[str, str] = {}
    for row in expiry_data.data or []:
        store = row["store_name"]
        exp = row["expires_at"]
        if store not in store_expiry or exp > store_expiry[store]:
            store_expiry[store] = exp

    for sched in store_schedules:
        exp = store_expiry.get(sched["store"])
        if exp:
            sched["offers_valid_until"] = exp[:10]
            days_left = (datetime.fromisoformat(exp.replace("Z", "+00:00")) - now).days
            sched["days_until_expiry"] = max(days_left, 0)
        else:
            sched["offers_valid_until"] = None
            sched["days_until_expiry"] = None

    # Product-specific timing (if requested and enough history)
    product_timing = None
    if product_name:
        product_timing = await _analyze_product_timing(db, product_name, now)

    # User's top products timing
    user_insights = []
    try:
        patterns = (
            db.table("user_product_patterns")
            .select("normalized_name, purchase_count, avg_days_between_purchases, last_purchased_at")
            .eq("user_id", user_id)
            .order("purchase_count", desc=True)
            .limit(5)
            .execute()
        )
        for p in patterns.data or []:
            name = p["normalized_name"]
            avg_days = p.get("avg_days_between_purchases")
            last = p.get("last_purchased_at")
            insight = {"product": name, "purchase_count": p["purchase_count"]}

            if avg_days and last:
                try:
                    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                    next_buy = last_dt + timedelta(days=int(avg_days))
                    days_until = (next_buy - now).days
                    insight["avg_days_between"] = int(avg_days)
                    insight["next_expected_purchase"] = next_buy.date().isoformat()
                    insight["days_until_restock"] = max(days_until, 0)
                    if days_until <= 0:
                        insight["status"] = "due"
                    elif days_until <= 3:
                        insight["status"] = "soon"
                    else:
                        insight["status"] = "ok"
                except (ValueError, TypeError):
                    insight["status"] = "unknown"
            else:
                insight["status"] = "unknown"

            user_insights.append(insight)
    except Exception:
        pass

    result = {
        "store_schedules": store_schedules,
        "product_timing": product_timing,
        "user_restock_insights": user_insights,
        "data_weeks": 1,  # Will grow as scrapers run
        "needs_more_data": True,  # Will be False once we have 4+ weeks
    }

    set_cache(cache_key, result, ttl_seconds=600)
    return result


async def _analyze_product_timing(db, product_name: str, now: datetime) -> dict:
    """Analyze price history for a product to detect cycles."""
    from app.services.search_service import _normalize_for_grouping, _token_similarity

    words = product_name.lower().split()[:3]
    pattern = "%" + "%".join(words) + "%"

    # Get price history
    history = (
        db.table("price_history")
        .select("store_name, unit_price, observed_at, week_number, year_number")
        .ilike("product_name", pattern)
        .order("observed_at")
        .limit(200)
        .execute()
    )

    if not history.data or len(history.data) < 2:
        # Not enough data — show current status
        current = db.rpc(
            "search_products",
            {"p_query": pattern, "p_source": "leaflet", "p_limit": 5},
        ).execute()
        return {
            "product": product_name,
            "has_cycle_data": False,
            "message": "Not enough history yet — check back after 4 weeks of tracking",
            "current_offers": [
                {
                    "store": r["store_name"],
                    "price": float(r["unit_price"]),
                    "on_offer": r.get("is_on_offer", False),
                    "expires": r.get("expires_at", "")[:10],
                }
                for r in (current.data or [])
            ],
        }

    # Group by store and week
    by_store: dict[str, list[dict]] = {}
    for row in history.data:
        store = row["store_name"]
        if store not in by_store:
            by_store[store] = []
        by_store[store].append(row)

    store_analysis = []
    for store, records in by_store.items():
        prices = [float(r["unit_price"]) for r in records]
        weeks = sorted(set(r["week_number"] for r in records))
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)

        analysis = {
            "store": store,
            "avg_price": round(avg_price, 2),
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2),
            "weeks_tracked": len(weeks),
            "price_variance": round(max_price - min_price, 2),
        }

        # Detect cycle if 4+ weeks
        if len(weeks) >= 4:
            # Find weeks where price was below average (on sale)
            sale_weeks = [
                r["week_number"]
                for r in records
                if float(r["unit_price"]) < avg_price * 0.9
            ]
            if len(sale_weeks) >= 2:
                # Calculate average gap between sales
                gaps = [
                    sale_weeks[i + 1] - sale_weeks[i]
                    for i in range(len(sale_weeks) - 1)
                    if sale_weeks[i + 1] > sale_weeks[i]
                ]
                if gaps:
                    avg_gap = sum(gaps) / len(gaps)
                    last_sale_week = max(sale_weeks)
                    current_week = now.isocalendar()[1]
                    weeks_since_sale = current_week - last_sale_week
                    weeks_until_sale = max(0, int(avg_gap) - weeks_since_sale)

                    analysis["cycle_weeks"] = round(avg_gap, 1)
                    analysis["weeks_until_predicted_sale"] = weeks_until_sale
                    analysis["predicted_sale_price"] = round(min_price, 2)

        store_analysis.append(analysis)

    return {
        "product": product_name,
        "has_cycle_data": any(
            a.get("weeks_tracked", 0) >= 4 for a in store_analysis
        ),
        "stores": store_analysis,
    }


def _next_weekday(now: datetime, weekday: int) -> datetime:
    """Next occurrence of a weekday (0=Mon, 3=Thu, etc)."""
    from datetime import timedelta
    days_ahead = weekday - now.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (now + timedelta(days=days_ahead)).replace(
        hour=7, minute=0, second=0, microsecond=0,
    )


def _next_odd_day(now: datetime) -> datetime:
    """Next odd calendar day."""
    from datetime import timedelta
    d = now + timedelta(days=1)
    while d.day % 2 == 0:
        d += timedelta(days=1)
    return d.replace(hour=6, minute=0, second=0, microsecond=0)


def _next_even_day(now: datetime) -> datetime:
    """Next even calendar day."""
    from datetime import timedelta
    d = now + timedelta(days=1)
    while d.day % 2 != 0:
        d += timedelta(days=1)
    return d.replace(hour=7, minute=0, second=0, microsecond=0)


@router.post("/categorize-batch")
async def categorize_batch(
    batch_size: int = Query(50, ge=10, le=100),
    user_id: str = Depends(get_current_user),
):
    """Categorize products that have category='Other' using GPT.

    Processes a batch at a time. Run repeatedly to categorize all.
    Uses gpt-4.1-nano for cost efficiency (~$0.001 per 50 products).
    """
    import asyncio
    count = await _run_categorization_batch(batch_size)
    return {"categorized": count, "batch_size": batch_size}


async def _run_categorization_batch(batch_size: int = 50) -> int:
    """Categorize a batch of 'Other' products using GPT."""
    import json as json_mod
    import logging
    import re
    from openai import AsyncOpenAI

    log = logging.getLogger(__name__)
    db = get_service_client()
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # Get uncategorized products
    result = (
        db.table("collective_prices")
        .select("id, product_name")
        .eq("category", "Other")
        .eq("source", "leaflet")
        .limit(batch_size)
        .execute()
    )

    if not result.data:
        return 0

    products = result.data
    product_list = "\n".join(
        f"{i+1}. {p['product_name']}" for i, p in enumerate(products)
    )

    prompt = f"""Categorize each grocery product into exactly ONE category.

Categories:
- Fruit & Veg (fresh produce, salads, herbs)
- Dairy (milk, cheese, yogurt, butter, cream, eggs)
- Meat & Fish (fresh/frozen meat, poultry, fish, seafood)
- Bakery (bread, rolls, cakes, pastries, biscuits, crackers)
- Frozen (frozen meals, frozen veg, ice cream, frozen pizza)
- Drinks (water, juice, soft drinks, tea, coffee, energy drinks)
- Snacks & Confectionery (chocolate, sweets, crisps, nuts, bars, cereal bars)
- Household (cleaning, detergent, bleach, kitchen rolls, bin bags, foil)
- Personal Care (shampoo, soap, toothpaste, deodorant, skincare, haircare)
- Baby & Kids (baby food, nappies, baby care, kids snacks)
- Pet Food (dog food, cat food, pet treats)
- Alcohol (beer, wine, spirits, cider)
- Pantry (canned goods, pasta, rice, sauce, soup, oil, spices, spreads, cereal, condiments)

IMPORTANT: Almost nothing should be "Other". Use "Pantry" for canned/jarred/packaged staples.

Reply with ONLY number and category per line:
1. Snacks & Confectionery
2. Personal Care

Products:
{product_list}"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4.1-nano",
            max_completion_tokens=batch_size * 15,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response.choices[0].message.content.strip()

        valid_categories = {
            "fruit & veg", "dairy", "meat & fish", "bakery", "frozen",
            "drinks", "snacks & confectionery", "household", "personal care",
            "baby & kids", "pet food", "alcohol", "pantry", "other",
        }

        updated = 0
        for line in answer.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Flexible parse: "1. Dairy" or "1 - Dairy" or "1) Dairy"
            m = re.match(r"^(\d+)[.\-)\s]+(.+)$", line)
            if not m:
                continue
            try:
                idx = int(m.group(1)) - 1
                category = m.group(2).strip().rstrip(".")
                if 0 <= idx < len(products) and category.lower() in valid_categories:
                    # If GPT says "Other", mark as "Uncategorized" so it won't loop
                    final_cat = "Uncategorized" if category.lower() == "other" else category
                    db.table("collective_prices").update(
                        {"category": final_cat}
                    ).eq("id", products[idx]["id"]).execute()
                    updated += 1
            except (ValueError, IndexError):
                pass

        log.info(f"Categorized {updated}/{len(products)} products")
        return updated

    except Exception as e:
        log.warning(f"Categorization batch failed: {e}")
        return 0


# ── Product Confirmation (5th Layer) ──────────────────────────────────────
@router.get("/confirmations/pending")
async def get_pending_confirmations(
    user_id: str = Depends(get_current_user),
):
    """Get products needing user confirmation — 'Is this the same product?'"""
    db = get_service_client()

    pending = (
        db.table("price_match_confirmations")
        .select("*")
        .eq("user_id", user_id)
        .is_("confirmed", "null")
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )

    return {
        "pending": pending.data or [],
        "count": len(pending.data or []),
    }


@router.post("/confirmations/{confirmation_id}")
async def respond_to_confirmation(
    confirmation_id: str,
    confirmed: bool = True,
    user_id: str = Depends(get_current_user),
):
    """User confirms or rejects a product match.

    If confirmed=True: the match is trusted, prices comparison improves.
    If confirmed=False: the match is rejected, won't be shown again.
    """
    from datetime import datetime, timezone

    db = get_service_client()

    # Verify ownership
    record = (
        db.table("price_match_confirmations")
        .select("id, user_id")
        .eq("id", confirmation_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not record.data:
        raise HTTPException(status_code=404, detail="Confirmation not found")

    db.table("price_match_confirmations").update({
        "confirmed": confirmed,
        "responded_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", confirmation_id).execute()

    return {
        "status": "confirmed" if confirmed else "rejected",
        "id": confirmation_id,
    }


@router.get("/store-products")
async def get_store_products(
    q: str = Query(..., min_length=2),
    store: str = Query(...),
    limit: int = Query(20, ge=1, le=50),
    user_id: str = Depends(get_current_user),
):
    """Get all products matching query at a specific store.

    Used when user taps a store in the comparison view to see
    all variants/sizes available at that store.
    """
    db = get_service_client()
    words = q.split()
    pattern = "%" + "%".join(words) + "%"

    try:
        result = db.rpc(
            "search_products",
            {"p_query": pattern, "p_limit": limit},
        ).execute()
    except Exception as e:
        return {"store": store, "products": [], "total": 0}

    # Filter to exact store and apply word-boundary check
    search_words = [w.lower() for w in q.split() if len(w) >= 2]
    products = []
    for row in (result.data or []):
        if row["store_name"].lower() != store.lower():
            continue
        # Word boundary check
        name_lower = " " + row["product_name"].lower() + " "
        match = True
        for sw in search_words:
            if f" {sw}" not in name_lower and not name_lower.lstrip().startswith(sw):
                match = False
                break
        if match:
            from app.services.search_service import _per_unit_price
            pup = _per_unit_price(float(row["unit_price"]), row["product_name"])
            products.append({
                "product_name": row["product_name"],
                "product_key": row.get("product_key", ""),
                "unit_price": float(row["unit_price"]),
                "is_on_offer": row.get("is_on_offer", False),
                "price_per_100": round(pup * 100, 2) if pup else None,
            })

    products.sort(key=lambda x: x["unit_price"])

    return {
        "store": store,
        "query": q,
        "products": products,
        "total": len(products),
    }
