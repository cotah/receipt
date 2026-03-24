from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from app.utils.auth_utils import get_current_user
from app.utils.text_utils import generate_product_key
from app.database import get_service_client
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
    user_id: str = Depends(get_current_user),
):
    db = get_service_client()
    now = datetime.now(timezone.utc)

    query = (
        db.table("collective_prices")
        .select("*")
        .eq("source", "leaflet")
        .gte("expires_at", now.isoformat())
        .order("unit_price")
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

    return LeafletOffersResponse(valid_until=max_valid, offers=offers)
