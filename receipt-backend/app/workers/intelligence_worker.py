"""
SmartDocket Intelligence Worker
Computes weekly deals, refreshes analytics, and maintains price intelligence.
Runs every 3 days at 03:00 UTC.
"""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import get_service_client

log = logging.getLogger(__name__)


async def compute_global_deals(db) -> int:
    """Compute top 4 global deals: products with biggest discount vs 4-week avg."""
    now = datetime.now(timezone.utc)
    four_weeks_ago = (now - timedelta(weeks=4)).isoformat()
    valid_until = (now + timedelta(days=3)).isoformat()

    try:
        current = (
            db.table("collective_prices")
            .select(
                "product_key, product_name, store_name, "
                "unit_price, category, is_on_offer"
            )
            .eq("source", "leaflet")
            .gte("expires_at", now.isoformat())
            .execute()
        )

        if not current.data:
            log.warning("No current leaflet prices for global deals")
            return 0

        deals = []
        for item in current.data:
            pk = item["product_key"]
            store = item["store_name"]

            history = (
                db.table("price_history")
                .select("unit_price")
                .eq("product_key", pk)
                .eq("store_name", store)
                .gte("observed_at", four_weeks_ago)
                .execute()
            )

            if not history.data or len(history.data) < 2:
                continue

            prices = [h["unit_price"] for h in history.data]
            avg_4w = sum(prices) / len(prices)
            current_price = item["unit_price"]

            if avg_4w <= 0 or current_price >= avg_4w:
                continue

            discount_pct = int(round((1 - current_price / avg_4w) * 100))
            if discount_pct < 5:
                continue

            deals.append(
                {
                    "product_key": pk,
                    "product_name": item["product_name"],
                    "store_name": store,
                    "current_price": current_price,
                    "avg_price_4w": round(avg_4w, 2),
                    "discount_pct": discount_pct,
                    "category": item["category"],
                    "deal_type": "global",
                    "valid_until": valid_until,
                    "computed_at": now.isoformat(),
                }
            )

        deals.sort(key=lambda d: d["discount_pct"], reverse=True)
        top4 = deals[:4]

        if not top4:
            log.info("No qualifying global deals found this cycle")
            return 0

        db.table("weekly_deals").delete().is_("user_id", "null").execute()
        for rank, deal in enumerate(top4, start=1):
            deal["rank"] = rank
            db.table("weekly_deals").insert(deal).execute()

        log.info("Computed %d global deals", len(top4))
        return len(top4)

    except Exception as e:
        log.error("compute_global_deals failed: %s", e)
        return 0


async def compute_personalised_deals(db) -> int:
    """Compute top 6 personalised deals per user."""
    now = datetime.now(timezone.utc)
    valid_until = (now + timedelta(days=3)).isoformat()
    total = 0

    try:
        ninety_days_ago = (now - timedelta(days=90)).isoformat()
        active_users = (
            db.table("receipts")
            .select("user_id")
            .gte("purchased_at", ninety_days_ago)
            .execute()
        )

        user_ids = list(
            {r["user_id"] for r in (active_users.data or [])}
        )
        log.info(
            "Computing personalised deals for %d active users",
            len(user_ids),
        )

        global_deals = (
            db.table("weekly_deals")
            .select("product_key")
            .is_("user_id", "null")
            .execute()
        )
        global_keys = {
            d["product_key"] for d in (global_deals.data or [])
        }

        current_prices = (
            db.table("collective_prices")
            .select(
                "product_key, product_name, store_name, "
                "unit_price, category, is_on_offer"
            )
            .eq("source", "leaflet")
            .gte("expires_at", now.isoformat())
            .execute()
        )

        price_map: dict[str, list] = {}
        for p in current_prices.data or []:
            pk = p["product_key"]
            if pk not in price_map:
                price_map[pk] = []
            price_map[pk].append(p)

        for user_id in user_ids:
            try:
                patterns = (
                    db.table("user_product_patterns")
                    .select(
                        "normalized_name, category, "
                        "purchase_count, avg_price, min_price_ever"
                    )
                    .eq("user_id", user_id)
                    .gte("purchase_count", 2)
                    .execute()
                )

                if not patterns.data:
                    continue

                from app.utils.text_utils import generate_product_key

                user_deals = []
                for pattern in patterns.data:
                    pk = generate_product_key(pattern["normalized_name"])

                    if pk in global_keys or pk not in price_map:
                        continue

                    best = min(
                        price_map[pk], key=lambda x: x["unit_price"]
                    )
                    current_price = best["unit_price"]
                    user_avg = pattern.get("avg_price") or 0

                    if user_avg <= 0 or current_price >= user_avg:
                        continue

                    discount_pct = int(
                        round((1 - current_price / user_avg) * 100)
                    )
                    if discount_pct < 5:
                        continue

                    user_deals.append(
                        {
                            "user_id": user_id,
                            "product_key": pk,
                            "product_name": pattern["normalized_name"],
                            "store_name": best["store_name"],
                            "current_price": current_price,
                            "avg_price_4w": round(user_avg, 2),
                            "min_price_ever": pattern.get(
                                "min_price_ever"
                            ),
                            "discount_pct": discount_pct,
                            "category": pattern["category"],
                            "deal_type": "personalised",
                            "valid_until": valid_until,
                            "computed_at": now.isoformat(),
                        }
                    )

                user_deals.sort(
                    key=lambda d: d["discount_pct"], reverse=True
                )
                top6 = user_deals[:6]

                if not top6:
                    continue

                db.table("weekly_deals").delete().eq(
                    "user_id", user_id
                ).execute()

                for rank, deal in enumerate(top6, start=1):
                    deal["rank"] = rank
                    db.table("weekly_deals").insert(deal).execute()

                total += len(top6)

            except Exception as e:
                log.warning(
                    "Personalised deals failed for user %s: %s",
                    user_id,
                    e,
                )
                continue

        log.info(
            "Computed %d personalised deals across %d users",
            total,
            len(user_ids),
        )
        return total

    except Exception as e:
        log.error("compute_personalised_deals failed: %s", e)
        return 0


async def refresh_rag_context(db) -> None:
    """Generate a global analytics summary for the RAG system."""
    now = datetime.now(timezone.utc)

    try:
        popular = (
            db.table("popular_products_this_month")
            .select(
                "normalized_name, category, "
                "purchase_count, unique_buyers"
            )
            .limit(20)
            .execute()
        )
        stores = db.table("store_popularity").select("*").execute()
        hours = (
            db.table("shopping_hour_distribution")
            .select("*")
            .order("receipt_count", desc=True)
            .limit(5)
            .execute()
        )

        popular_list = ", ".join(
            f"{p['normalized_name']} ({p['purchase_count']} buys)"
            for p in (popular.data or [])[:10]
        )
        store_list = ", ".join(
            f"{s['store_name']} ({s['visit_count']} visits)"
            for s in (stores.data or [])
        )
        peak_hours = ", ".join(
            f"{h['hour_of_day']}:00 ({h['pct']}%)"
            for h in (hours.data or [])[:3]
        )

        summary = (
            f"Global SmartDocket snapshot ({now.strftime('%Y-%m-%d')}): "
            f"Top products this month: {popular_list}. "
            f"Store popularity: {store_list}. "
            f"Peak shopping hours: {peak_hours}."
        )

        db.table("chat_messages").upsert(
            {
                "user_id": "00000000-0000-0000-0000-000000000000",
                "session_id": "__rag_global_context__",
                "role": "system",
                "content": summary,
                "created_at": now.isoformat(),
            },
            on_conflict="user_id,session_id,role",
        ).execute()

        log.info("RAG global context refreshed: %d chars", len(summary))

    except Exception as e:
        log.warning("refresh_rag_context failed: %s", e)


async def run_intelligence_job():
    """Main intelligence job — runs every 3 days."""
    log.info("Intelligence worker starting...")
    db = get_service_client()

    global_count = await compute_global_deals(db)
    persona_count = await compute_personalised_deals(db)
    await refresh_rag_context(db)

    log.info(
        "Intelligence worker complete: %d global deals, "
        "%d personalised deals computed",
        global_count,
        persona_count,
    )


def setup_intelligence_scheduler(scheduler: AsyncIOScheduler):
    """Schedule intelligence job every 3 days at 03:00 UTC."""
    scheduler.add_job(
        run_intelligence_job,
        "cron",
        hour=3,
        minute=0,
        day="*/3",
        id="intelligence_worker",
        replace_existing=True,
    )
    log.info("Intelligence worker scheduled: every 3 days at 03:00 UTC")
