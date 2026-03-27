"""Offers Engine — generates smart weekly deals for each user.

Deal types:
- global  (4): Trending products — best cross-store savings, most popular
- personalised (6 PRO / 2 FREE): Products matching user's purchase history
- golden  (3, PRO only): Exceptional deals — price >25% below 8-week average

Runs every 2 days (PRO refresh) / deals valid for 4 days (FREE cadence).
"""

import logging
import random
from datetime import datetime, timedelta, timezone

from openai import AsyncOpenAI

from app.config import settings
from app.database import get_service_client

log = logging.getLogger(__name__)

_ai_client = None


def _get_ai():
    global _ai_client
    if _ai_client is None and settings.OPENAI_API_KEY:
        _ai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _ai_client


# ---------------------------------------------------------------------------
# 1. TRENDING ENGINE — 4 global deals (same for everyone)
# ---------------------------------------------------------------------------

async def _generate_trending_deals(db, count: int = 4) -> list[dict]:
    """Find the best trending deals based on:
    - Products available at 2+ stores with biggest price gap (smart grouping)
    - Products with is_on_offer=true
    - Cross-store savings opportunities
    """
    from app.services.search_service import _normalize_for_grouping, _token_similarity

    now = datetime.now(timezone.utc)
    deals = []
    seen_keys: set[str] = set()

    # Get all on-offer products
    try:
        offers = (
            db.table("collective_prices")
            .select("product_key, product_name, store_name, unit_price, is_on_offer, category")
            .eq("source", "leaflet")
            .eq("is_on_offer", True)
            .gte("expires_at", now.isoformat())
            .order("unit_price")
            .limit(500)
            .execute()
        )
    except Exception as e:
        log.error("Trending: failed to fetch offers: %s", e)
        return []

    # Smart grouping: normalize names and find same product across stores
    groups: list[dict] = []
    for row in offers.data or []:
        norm = _normalize_for_grouping(row["product_name"])
        entry = {
            "product_key": row["product_key"],
            "product_name": row["product_name"],
            "store_name": row["store_name"],
            "unit_price": float(row["unit_price"]),
            "category": row.get("category", "Other"),
        }

        matched = False
        for group in groups:
            if _token_similarity(norm, group["norm"]) >= 0.6:
                existing_stores = {s["store_name"] for s in group["stores"]}
                if entry["store_name"] not in existing_stores:
                    group["stores"].append(entry)
                matched = True
                break

        if not matched:
            groups.append({"norm": norm, "stores": [entry]})

    # Find groups with biggest cross-store savings
    savings_list: list[tuple[float, dict]] = []
    for group in groups:
        if len(group["stores"]) < 2:
            continue
        group["stores"].sort(key=lambda s: s["unit_price"])
        cheapest = group["stores"][0]
        expensive = group["stores"][-1]
        saving = expensive["unit_price"] - cheapest["unit_price"]
        if saving > 0.20 and cheapest["unit_price"] > 0.30:
            pct = saving / expensive["unit_price"] * 100
            savings_list.append((pct, {
                "cheapest": cheapest,
                "expensive": expensive,
                "pct": pct,
                "saving": saving,
            }))

    savings_list.sort(key=lambda x: -x[0])

    for pct, match in savings_list[:count]:
        c = match["cheapest"]
        e = match["expensive"]
        if c["product_key"] in seen_keys:
            continue
        seen_keys.add(c["product_key"])
        deals.append({
            "product_key": c["product_key"],
            "product_name": c["product_name"],
            "store_name": c["store_name"],
            "current_price": c["unit_price"],
            "avg_price_4w": e["unit_price"],
            "discount_pct": int(match["pct"]),
            "category": c.get("category", "Other"),
            "deal_type": "global",
            "promotion_text": (
                f"Save {match['pct']:.0f}% — €{c['unit_price']:.2f} at "
                f"{c['store_name']} vs €{e['unit_price']:.2f} at {e['store_name']}"
            ),
        })

    # Fill remaining slots with cheapest on-offer products (>€0.50 to avoid junk)
    if len(deals) < count:
        cheap_offers = [
            r for r in (offers.data or [])
            if r["product_key"] not in seen_keys and float(r["unit_price"]) >= 0.50
        ]
        for row in cheap_offers:
            if len(deals) >= count:
                break
            seen_keys.add(row["product_key"])
            deals.append({
                "product_key": row["product_key"],
                "product_name": row["product_name"],
                "store_name": row["store_name"],
                "current_price": float(row["unit_price"]),
                "avg_price_4w": None,
                "discount_pct": None,
                "category": row.get("category", "Other"),
                "deal_type": "global",
                "promotion_text": f"On offer at {row['store_name']}",
            })

    log.info("Trending engine: generated %d deals", len(deals))
    return deals[:count]


# ---------------------------------------------------------------------------
# 2. PERSONAL ENGINE — deals matching user's purchase history
# ---------------------------------------------------------------------------

async def _generate_personal_deals(
    db, user_id: str, count: int = 6
) -> list[dict]:
    """Find deals matching the user's purchase patterns.

    Strategy:
    1. Get user's frequently purchased products from user_product_patterns
    2. Match against current offers in collective_prices
    3. If user has no history, use AI to suggest based on popular categories
    """
    now = datetime.now(timezone.utc)
    deals = []
    seen_keys: set[str] = set()

    # Step 1: Get user's purchase patterns
    try:
        patterns = (
            db.table("user_product_patterns")
            .select("normalized_name, category, purchase_count, avg_price")
            .eq("user_id", user_id)
            .order("purchase_count", desc=True)
            .limit(30)
            .execute()
        )
        user_products = patterns.data or []
    except Exception:
        user_products = []

    # Step 2: Get recent receipt items as fallback
    if not user_products:
        try:
            recent_items = (
                db.table("receipt_items")
                .select("normalized_name, category, unit_price")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(20)
                .execute()
            )
            user_products = [
                {"normalized_name": r["normalized_name"], "category": r["category"],
                 "purchase_count": 1, "avg_price": r["unit_price"]}
                for r in (recent_items.data or [])
            ]
        except Exception:
            user_products = []

    # Step 3: Match user products against current offers
    if user_products:
        for prod in user_products:
            if len(deals) >= count:
                break
            name = prod["normalized_name"]
            avg_price = float(prod.get("avg_price") or 0)

            # Strategy A: ILIKE text match (fast, exact)
            words = name.lower().split()[:3]
            pattern = "%" + "%".join(words) + "%"
            matched = False
            try:
                matches = (
                    db.table("collective_prices")
                    .select("product_key, product_name, store_name, unit_price, is_on_offer, category")
                    .eq("source", "leaflet")
                    .gte("expires_at", now.isoformat())
                    .ilike("product_name", pattern)
                    .order("unit_price")
                    .limit(3)
                    .execute()
                )
                for m in matches.data or []:
                    if m["product_key"] in seen_keys:
                        continue
                    seen_keys.add(m["product_key"])
                    current = float(m["unit_price"])
                    saving_pct = None
                    if avg_price > 0 and current < avg_price:
                        saving_pct = int((avg_price - current) / avg_price * 100)

                    deals.append({
                        "product_key": m["product_key"],
                        "product_name": m["product_name"],
                        "store_name": m["store_name"],
                        "current_price": current,
                        "avg_price_4w": avg_price if avg_price > 0 else None,
                        "discount_pct": saving_pct,
                        "category": m.get("category", "Other"),
                        "deal_type": "personalised",
                        "promotion_text": (
                            f"You buy this regularly — now €{current:.2f} at {m['store_name']}"
                            if not saving_pct else
                            f"You usually pay €{avg_price:.2f} — now €{current:.2f} ({saving_pct}% cheaper)"
                        ),
                    })
                    matched = True
                    break
            except Exception as e:
                log.warning("Personal deals: ILIKE match failed for '%s': %s", name, e)

            # Strategy B: Embedding similarity (smart, catches "Milk 2L" → "Fresh Milk")
            if not matched:
                try:
                    from app.services.embedding_service import find_similar_products
                    similar = await find_similar_products(
                        f"{name} {prod.get('category', '')}",
                        threshold=0.75,
                        limit=3,
                    )
                    for s in similar:
                        pkey = s.get("product_name", "").lower().replace(" ", "_")
                        if pkey in seen_keys:
                            continue
                        seen_keys.add(pkey)
                        current = float(s["unit_price"])
                        saving_pct = None
                        if avg_price > 0 and current < avg_price:
                            saving_pct = int((avg_price - current) / avg_price * 100)

                        deals.append({
                            "product_key": pkey,
                            "product_name": s["product_name"],
                            "store_name": s["store_name"],
                            "current_price": current,
                            "avg_price_4w": avg_price if avg_price > 0 else None,
                            "discount_pct": saving_pct,
                            "category": s.get("category", "Other"),
                            "deal_type": "personalised",
                            "promotion_text": (
                                f"Similar to what you buy — €{current:.2f} at {s['store_name']}"
                                if not saving_pct else
                                f"You usually pay €{avg_price:.2f} for similar — now €{current:.2f} ({saving_pct}% cheaper)"
                            ),
                        })
                        break
                except Exception as e:
                    log.debug("Personal deals: embedding match failed for '%s': %s", name, e)

    # Step 4: AI fallback — if not enough deals from purchase history
    if len(deals) < count:
        ai_deals = await _ai_suggest_deals(db, user_id, count - len(deals), seen_keys)
        deals.extend(ai_deals)

    log.info("Personal engine [%s]: generated %d deals", user_id[:8], len(deals))
    return deals[:count]


async def _ai_suggest_deals(
    db, user_id: str, count: int, seen_keys: set[str]
) -> list[dict]:
    """Use AI to suggest relevant deals when user has little purchase history."""
    now = datetime.now(timezone.utc)
    client = _get_ai()
    if not client:
        return _fallback_random_deals(db, count, seen_keys)

    try:
        # Get some context about the user
        profile = (
            db.table("profiles")
            .select("full_name, home_area")
            .eq("id", user_id)
            .single()
            .execute()
        )
        area = (profile.data or {}).get("home_area", "Dublin")

        response = await client.chat.completions.create(
            model="gpt-5.4-nano",
            temperature=0.5,
            max_completion_tokens=150,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a grocery shopping assistant for Ireland. "
                        "Suggest 5 common grocery product search terms that an "
                        "Irish household would typically buy weekly. "
                        "Return ONLY the terms, one per line, 1-3 words each. "
                        "Focus on everyday essentials like milk, bread, fruit, etc."
                    ),
                },
                {"role": "user", "content": f"Location: {area}. Suggest weekly essentials."},
            ],
        )
        terms = [
            line.strip()
            for line in (response.choices[0].message.content or "").split("\n")
            if line.strip()
        ]
    except Exception as e:
        log.warning("AI suggest deals failed: %s", e)
        return _fallback_random_deals(db, count, seen_keys)

    deals = []
    for term in terms[:count + 2]:
        if len(deals) >= count:
            break
        try:
            words = term.lower().split()
            pattern = "%" + "%".join(words) + "%"
            matches = (
                db.table("collective_prices")
                .select("product_key, product_name, store_name, unit_price, is_on_offer, category")
                .eq("source", "leaflet")
                .eq("is_on_offer", True)
                .gte("expires_at", now.isoformat())
                .ilike("product_name", pattern)
                .order("unit_price")
                .limit(1)
                .execute()
            )
            for m in matches.data or []:
                if m["product_key"] not in seen_keys:
                    seen_keys.add(m["product_key"])
                    deals.append({
                        "product_key": m["product_key"],
                        "product_name": m["product_name"],
                        "store_name": m["store_name"],
                        "current_price": float(m["unit_price"]),
                        "avg_price_4w": None,
                        "discount_pct": None,
                        "category": m.get("category", "Other"),
                        "deal_type": "personalised",
                        "promotion_text": f"Popular this week — €{float(m['unit_price']):.2f} at {m['store_name']}",
                    })
        except Exception:
            pass

    return deals


def _fallback_random_deals(db, count: int, seen_keys: set[str]) -> list[dict]:
    """Fallback when AI is unavailable — pick random cheap offers."""
    now = datetime.now(timezone.utc)
    try:
        cheap = (
            db.table("collective_prices")
            .select("product_key, product_name, store_name, unit_price, is_on_offer, category")
            .eq("source", "leaflet")
            .eq("is_on_offer", True)
            .gte("expires_at", now.isoformat())
            .order("unit_price")
            .limit(50)
            .execute()
        )
        candidates = [
            r for r in (cheap.data or [])
            if r["product_key"] not in seen_keys and float(r["unit_price"]) > 0.50
        ]
        random.shuffle(candidates)
        deals = []
        for m in candidates[:count]:
            seen_keys.add(m["product_key"])
            deals.append({
                "product_key": m["product_key"],
                "product_name": m["product_name"],
                "store_name": m["store_name"],
                "current_price": float(m["unit_price"]),
                "avg_price_4w": None,
                "discount_pct": None,
                "category": m.get("category", "Other"),
                "deal_type": "personalised",
                "promotion_text": f"Great value — €{float(m['unit_price']):.2f} at {m['store_name']}",
            })
        return deals
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 3. GOLDEN OFFER ENGINE — PRO only, exceptional deals
# ---------------------------------------------------------------------------

async def _generate_golden_deals(
    db, user_id: str, count: int = 3
) -> list[dict]:
    """Find exceptional deals — products significantly below their recent average.

    A golden deal is:
    - Current price is >25% below the 8-week average
    - Product matches user's interests (from patterns or AI)
    """
    now = datetime.now(timezone.utc)
    eight_weeks_ago = (now - timedelta(weeks=8)).isoformat()
    deals = []
    seen_keys: set[str] = set()

    # Get user's categories/interests for relevance filtering
    user_categories: set[str] = set()
    try:
        patterns = (
            db.table("user_product_patterns")
            .select("category")
            .eq("user_id", user_id)
            .execute()
        )
        for p in patterns.data or []:
            if p.get("category"):
                user_categories.add(p["category"])
    except Exception:
        pass

    # Get current offers with their historical average
    try:
        current_offers = (
            db.table("collective_prices")
            .select("product_key, product_name, store_name, unit_price, category")
            .eq("source", "leaflet")
            .eq("is_on_offer", True)
            .gte("expires_at", now.isoformat())
            .order("unit_price")
            .limit(200)
            .execute()
        )
    except Exception as e:
        log.error("Golden deals: failed to fetch offers: %s", e)
        return []

    # For each offer, check if it's significantly below historical average
    golden_candidates: list[tuple[float, dict]] = []

    for offer in current_offers.data or []:
        key = offer["product_key"]
        current = float(offer["unit_price"])
        if current < 0.50:  # skip very cheap items
            continue

        try:
            history = (
                db.table("price_history")
                .select("unit_price")
                .eq("product_key", key)
                .gte("observed_at", eight_weeks_ago)
                .execute()
            )
            prices = [float(r["unit_price"]) for r in (history.data or [])]
            if not prices:
                continue
            avg = sum(prices) / len(prices)
            if avg <= 0:
                continue
            discount_pct = (avg - current) / avg * 100
            if discount_pct >= 25:
                golden_candidates.append((discount_pct, {
                    **offer,
                    "avg_price_8w": round(avg, 2),
                    "discount_pct": int(discount_pct),
                }))
        except Exception:
            continue

    # Sort by discount percentage
    golden_candidates.sort(key=lambda x: -x[0])

    # Prefer products in user's categories
    categorized = []
    uncategorized = []
    for pct, cand in golden_candidates:
        if cand.get("category") in user_categories:
            categorized.append(cand)
        else:
            uncategorized.append(cand)

    candidates = categorized + uncategorized

    for cand in candidates[:count]:
        key = cand["product_key"]
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deals.append({
            "product_key": key,
            "product_name": cand["product_name"],
            "store_name": cand["store_name"],
            "current_price": float(cand["unit_price"]),
            "avg_price_4w": cand.get("avg_price_8w"),
            "min_price_ever": float(cand["unit_price"]),
            "discount_pct": cand["discount_pct"],
            "category": cand.get("category", "Other"),
            "deal_type": "golden",
            "promotion_text": (
                f"🥇 Golden Deal — {cand['discount_pct']}% below average! "
                f"€{float(cand['unit_price']):.2f} vs avg €{cand.get('avg_price_8w', 0):.2f}"
            ),
        })

    log.info("Golden engine [%s]: generated %d deals", user_id[:8], len(deals))
    return deals[:count]


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def generate_all_deals() -> dict:
    """Generate weekly deals for all users.

    Returns a summary of what was generated.
    """
    db = get_service_client()
    now = datetime.now(timezone.utc)
    stats = {"trending": 0, "personal": 0, "golden": 0, "users": 0}

    # 1. Generate trending deals (global, no user_id)
    trending = await _generate_trending_deals(db, count=4)
    stats["trending"] = len(trending)

    # 2. Get all users
    try:
        users = (
            db.table("profiles")
            .select("id, plan")
            .execute()
        )
    except Exception as e:
        log.error("Deals engine: failed to fetch users: %s", e)
        return stats

    # 3. Clear old deals
    try:
        db.table("weekly_deals").delete().gte("id", "00000000-0000-0000-0000-000000000000").execute()
        log.info("Deals engine: cleared old deals")
    except Exception as e:
        log.warning("Deals engine: failed to clear old deals: %s", e)

    # 4. Insert trending deals (global)
    valid_until_free = (now + timedelta(days=4)).isoformat()
    valid_until_pro = (now + timedelta(days=2)).isoformat()

    for i, deal in enumerate(trending):
        try:
            db.table("weekly_deals").insert({
                "user_id": None,
                "product_key": deal["product_key"],
                "product_name": deal["product_name"],
                "store_name": deal["store_name"],
                "current_price": deal["current_price"],
                "avg_price_4w": deal.get("avg_price_4w"),
                "discount_pct": deal.get("discount_pct"),
                "promotion_text": deal.get("promotion_text"),
                "category": deal.get("category", "Other"),
                "deal_type": "global",
                "rank": i + 1,
                "valid_from": now.isoformat(),
                "valid_until": valid_until_free,
                "computed_at": now.isoformat(),
            }).execute()
        except Exception as e:
            log.warning("Deals engine: failed to insert trending deal: %s", e)

    # 5. Generate personal + golden deals per user
    for user in users.data or []:
        user_id = user["id"]
        plan = user.get("plan", "free")
        stats["users"] += 1

        # Personal deals: 6 for pro, 2 for free
        personal_count = 6 if plan == "pro" else 2
        personal = await _generate_personal_deals(db, user_id, count=personal_count)
        stats["personal"] += len(personal)

        valid_until = valid_until_pro if plan == "pro" else valid_until_free

        for i, deal in enumerate(personal):
            try:
                db.table("weekly_deals").insert({
                    "user_id": user_id,
                    "product_key": deal["product_key"],
                    "product_name": deal["product_name"],
                    "store_name": deal["store_name"],
                    "current_price": deal["current_price"],
                    "avg_price_4w": deal.get("avg_price_4w"),
                    "discount_pct": deal.get("discount_pct"),
                    "promotion_text": deal.get("promotion_text"),
                    "category": deal.get("category", "Other"),
                    "deal_type": "personalised",
                    "rank": i + 1,
                    "valid_from": now.isoformat(),
                    "valid_until": valid_until,
                    "computed_at": now.isoformat(),
                }).execute()
            except Exception as e:
                log.warning("Deals engine: personal deal insert failed: %s", e)

        # Golden deals: PRO only
        if plan == "pro":
            golden = await _generate_golden_deals(db, user_id, count=3)
            stats["golden"] += len(golden)

            for i, deal in enumerate(golden):
                try:
                    db.table("weekly_deals").insert({
                        "user_id": user_id,
                        "product_key": deal["product_key"],
                        "product_name": deal["product_name"],
                        "store_name": deal["store_name"],
                        "current_price": deal["current_price"],
                        "avg_price_4w": deal.get("avg_price_4w"),
                        "min_price_ever": deal.get("min_price_ever"),
                        "discount_pct": deal.get("discount_pct"),
                        "promotion_text": deal.get("promotion_text"),
                        "category": deal.get("category", "Other"),
                        "deal_type": "golden",
                        "rank": i + 1,
                        "valid_from": now.isoformat(),
                        "valid_until": valid_until_pro,
                        "computed_at": now.isoformat(),
                    }).execute()
                except Exception as e:
                    log.warning("Deals engine: golden deal insert failed: %s", e)

            # Send push notification for golden deals
            if golden:
                try:
                    from app.services.push_service import send_golden_deal_alerts
                    sent = await send_golden_deal_alerts(db, golden, user_id)
                    if sent:
                        log.info("Golden alert sent to %s", user_id[:8])
                except Exception as e:
                    log.debug("Golden alert failed for %s: %s", user_id[:8], e)

    log.info(
        "Deals engine complete: %d trending, %d personal, %d golden for %d users",
        stats["trending"], stats["personal"], stats["golden"], stats["users"],
    )
    return stats


# ---------------------------------------------------------------------------
# Price history snapshot (runs after each scraper)
# ---------------------------------------------------------------------------

async def snapshot_prices_to_history() -> int:
    """Copy current collective_prices to price_history for trend analysis."""
    db = get_service_client()
    now = datetime.now(timezone.utc)
    week = now.isocalendar()[1]
    year = now.year
    count = 0

    try:
        prices = (
            db.table("collective_prices")
            .select("product_key, product_name, store_name, unit_price, source")
            .eq("source", "leaflet")
            .gte("expires_at", now.isoformat())
            .execute()
        )
        for row in prices.data or []:
            try:
                db.table("price_history").insert({
                    "product_key": row["product_key"],
                    "product_name": row["product_name"],
                    "store_name": row["store_name"],
                    "unit_price": float(row["unit_price"]),
                    "source": "scraper",
                    "observed_at": now.isoformat(),
                    "week_number": week,
                    "year_number": year,
                }).execute()
                count += 1
            except Exception:
                pass  # duplicate or constraint error, skip
    except Exception as e:
        log.error("Price snapshot failed: %s", e)

    log.info("Price snapshot: %d prices recorded (week %d/%d)", count, week, year)
    return count
