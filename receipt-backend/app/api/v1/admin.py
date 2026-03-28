"""Admin panel API — all routes require is_admin flag on profile."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel

from app.database import get_service_client
from app.utils.auth_utils import get_current_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


async def require_admin(request: Request) -> str:
    """Allow admin access via JWT (is_admin=true) or X-Admin-Key header."""
    from app.config import settings

    # Option 1: X-Admin-Key header
    admin_key = request.headers.get("X-Admin-Key", "")
    if admin_key and settings.ADMIN_KEY and admin_key == settings.ADMIN_KEY:
        return "admin-key-user"

    # Option 2: Bearer token (Supabase JWT)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            db = get_service_client()
            user_response = db.auth.get_user(token)
            if user_response and user_response.user:
                user_id = str(user_response.user.id)
                row = (
                    db.table("profiles")
                    .select("is_admin")
                    .eq("id", user_id)
                    .single()
                    .execute()
                )
                if row.data and row.data.get("is_admin"):
                    return user_id
        except Exception:
            pass

    raise HTTPException(status_code=403, detail="Admin access required")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class OverviewStats(BaseModel):
    total_users: int = 0
    pro_users: int = 0
    free_users: int = 0
    mrr: float = 0.0
    scans_today: int = 0
    scans_week: int = 0
    total_prices_in_db: int = 0
    active_scrapers: int = 0


class AdminUser(BaseModel):
    id: str
    email: str | None = None
    full_name: str | None = None
    plan: str = "free"
    scans_this_month: int = 0
    chat_queries_today: int = 0
    points: int = 0
    created_at: str | None = None


class ScraperInfo(BaseModel):
    name: str
    schedule: str
    last_run: str | None = None
    next_run: str | None = None
    items_count: int = 0
    status: str = "unknown"
    fallback_level: int = 0
    last_items_saved: int = 0
    last_error: str | None = None
    autofix_confidence: float | None = None


class UpgradeRequest(BaseModel):
    months: int = 12


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/stats")
async def admin_stats(_admin: str = Depends(require_admin)):
    db = get_service_client()
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    # User counts
    all_users = db.table("profiles").select("plan", count="exact").execute()
    total = all_users.count or 0
    pro_count = 0
    for u in all_users.data or []:
        if u.get("plan") == "pro":
            pro_count += 1

    # Scans today
    scans_today_q = (
        db.table("receipts")
        .select("id", count="exact")
        .gte("created_at", today_start.isoformat())
        .execute()
    )
    scans_today = scans_today_q.count or 0

    # Scans this week
    scans_week_q = (
        db.table("receipts")
        .select("id", count="exact")
        .gte("created_at", week_start.isoformat())
        .execute()
    )
    scans_week = scans_week_q.count or 0

    # Collective prices count
    prices_q = (
        db.table("collective_prices")
        .select("id", count="exact")
        .execute()
    )
    total_prices = prices_q.count or 0

    # Active scrapers (from APScheduler — count known jobs)
    active_scrapers = 5  # dunnes, supervalu, tesco, lidl, aldi

    return OverviewStats(
        total_users=total,
        pro_users=pro_count,
        free_users=total - pro_count,
        mrr=round(pro_count * 4.99, 2),
        scans_today=scans_today,
        scans_week=scans_week,
        total_prices_in_db=total_prices,
        active_scrapers=active_scrapers,
    )


@router.get("/users")
async def admin_users(
    search: str | None = None,
    plan: str | None = None,
    page: int = 1,
    per_page: int = 25,
    _admin: str = Depends(require_admin),
):
    db = get_service_client()
    query = db.table("profiles").select(
        "id, email, full_name, plan, scans_this_month, "
        "chat_queries_today, points, created_at",
        count="exact",
    ).order("created_at", desc=True)

    if plan and plan in ("free", "pro"):
        query = query.eq("plan", plan)
    if search:
        query = query.or_(f"email.ilike.%{search}%,full_name.ilike.%{search}%")

    offset = (page - 1) * per_page
    query = query.range(offset, offset + per_page - 1)
    result = query.execute()

    users = []
    for row in result.data or []:
        users.append(AdminUser(
            id=row["id"],
            email=row.get("email"),
            full_name=row.get("full_name"),
            plan=row.get("plan", "free"),
            scans_this_month=row.get("scans_this_month") or 0,
            chat_queries_today=row.get("chat_queries_today") or 0,
            points=row.get("points") or 0,
            created_at=row.get("created_at"),
        ))

    return {
        "users": users,
        "total": result.count or 0,
        "page": page,
        "per_page": per_page,
    }


SCRAPER_INFO = [
    {"name": "dunnes", "schedule": "Odd days at 05:00", "store": "Dunnes"},
    {"name": "supervalu", "schedule": "Odd days at 06:00", "store": "SuperValu"},
    {"name": "tesco", "schedule": "Even days at 07:00", "store": "Tesco"},
    {"name": "lidl", "schedule": "Thu at 07:00", "store": "Lidl"},
    {"name": "aldi", "schedule": "Thu at 08:00", "store": "Aldi"},
]


@router.get("/scrapers")
async def admin_scrapers(_admin: str = Depends(require_admin)):
    db = get_service_client()
    scrapers = []

    for s in SCRAPER_INFO:
        count_q = (
            db.table("collective_prices")
            .select("id", count="exact")
            .eq("store_name", s["store"])
            .eq("source", "leaflet")
            .execute()
        )
        items_count = count_q.count or 0

        # Last run from scraper_runs table
        run_q = (
            db.table("scraper_runs")
            .select("*")
            .eq("store_name", s["store"])
            .order("started_at", desc=True)
            .limit(1)
            .execute()
        )
        last = run_q.data[0] if run_q.data else None

        if last is None:
            status, fl, last_error, autofix_conf, last_saved = (
                "unknown", 0, None, None, 0
            )
        elif last["status"] == "success":
            fl = last.get("fallback_level", 0)
            status = "ok" if fl == 0 else "fallback"
            last_error, autofix_conf = None, None
            last_saved = last.get("items_saved", 0)
        else:
            status = "failed"
            fl = last.get("fallback_level", 0)
            last_error = last.get("error_detail")
            autofix_conf = last.get("autofix_confidence")
            last_saved = 0

        scrapers.append(ScraperInfo(
            name=s["name"],
            schedule=s["schedule"],
            last_run=last["finished_at"] if last else None,
            items_count=items_count,
            status=status,
            fallback_level=fl,
            last_items_saved=last_saved,
            last_error=last_error,
            autofix_confidence=autofix_conf,
        ))

    return {"scrapers": scrapers}


@router.get("/errors")
async def admin_errors(_admin: str = Depends(require_admin)):
    db = get_service_client()
    # Failed receipts as proxy for errors
    failed = (
        db.table("receipts")
        .select("id, user_id, store_name, status, created_at")
        .eq("status", "failed")
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    return {"errors": failed.data or []}


@router.post("/users/{user_id}/upgrade")
async def upgrade_user(
    user_id: str,
    body: UpgradeRequest | None = None,
    _admin: str = Depends(require_admin),
):
    months = body.months if body else 12
    db = get_service_client()
    expires = datetime.now(timezone.utc) + timedelta(days=months * 30)
    db.table("profiles").update({
        "plan": "pro",
        "plan_expires_at": expires.isoformat(),
    }).eq("id", user_id).execute()
    return {"status": "upgraded", "plan_expires_at": expires.isoformat()}


@router.post("/scrapers/{name}/run")
async def run_scraper(
    name: str,
    _admin: str = Depends(require_admin),
):
    import asyncio
    from app.workers.leaflet_worker import (
        run_dunnes_scraper,
        run_supervalu_scraper,
        run_tesco_scraper,
        run_lidl_scraper,
        run_leaflet_job,
    )

    runners = {
        "dunnes": run_dunnes_scraper,
        "supervalu": run_supervalu_scraper,
        "tesco": run_tesco_scraper,
        "lidl": run_lidl_scraper,
        "aldi": run_leaflet_job,
    }
    runner = runners.get(name)
    if not runner:
        raise HTTPException(status_code=404, detail=f"Unknown scraper: {name}")

    # Run in background
    asyncio.create_task(runner())
    return {"status": "started", "scraper": name}


@router.post("/scrapers/run-all")
async def run_all_scrapers(
    _admin: str = Depends(require_admin),
):
    import asyncio
    from app.workers.leaflet_worker import (
        run_dunnes_scraper,
        run_supervalu_scraper,
        run_tesco_scraper,
        run_lidl_scraper,
        run_leaflet_job,
    )

    all_runners = {
        "dunnes": run_dunnes_scraper,
        "supervalu": run_supervalu_scraper,
        "tesco": run_tesco_scraper,
        "lidl": run_lidl_scraper,
        "aldi": run_leaflet_job,
    }
    for name, runner in all_runners.items():
        asyncio.create_task(runner())
    return {"status": "started", "scrapers": list(all_runners.keys())}


@router.post("/cache/clear")
async def clear_cache(_admin: str = Depends(require_admin)):
    from app.services.cache_service import _get_redis
    redis = _get_redis()
    if redis:
        try:
            redis.flushdb()
            return {"status": "cleared"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}
    return {"status": "no_cache", "detail": "Redis not configured"}


@router.post("/email/test")
async def send_test_email(_admin: str = Depends(require_admin)):
    from app.services.email_service import send_email
    db = get_service_client()

    # When using admin key, look up the first admin user
    user_id = _admin
    if _admin == "admin-key-user":
        admins = db.table("profiles").select("id").eq("is_admin", True).limit(1).execute()
        if admins.data:
            user_id = admins.data[0]["id"]
        else:
            raise HTTPException(status_code=400, detail="No admin user found")

    profile = (
        db.table("profiles")
        .select("email, full_name")
        .eq("id", user_id)
        .single()
        .execute()
    )
    email = (profile.data or {}).get("email", "")
    name = (profile.data or {}).get("full_name", "Admin")
    if not email:
        raise HTTPException(status_code=400, detail="No email on profile")

    ok = await send_email(
        to=email,
        subject="SmartDocket Admin — Test Email",
        html=f"<h2>Test email</h2><p>Hi {name}, this is a test from the admin panel.</p>",
    )
    return {"status": "sent" if ok else "failed", "to": email}


@router.get("/activity")
async def admin_activity(_admin: str = Depends(require_admin)):
    """Scans per day for the last 14 days."""
    db = get_service_client()
    now = datetime.now(timezone.utc)
    days: list[dict] = []
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        next_day = day + timedelta(days=1)
        q = (
            db.table("receipts")
            .select("id", count="exact")
            .gte("created_at", day.isoformat())
            .lt("created_at", next_day.isoformat())
            .execute()
        )
        days.append({
            "date": day.strftime("%d/%m"),
            "scans": q.count or 0,
        })
    return {"days": days}


@router.get("/products/categories")
async def admin_product_categories(_admin: str = Depends(require_admin)):
    """Product count by category."""
    db = get_service_client()
    categories = [
        "Snacks & Confectionery", "Pantry", "Drinks", "Meat & Fish",
        "Personal Care", "Dairy", "Frozen", "Household", "Bakery",
        "Alcohol", "Fruit & Veg", "Baby & Kids", "Pet Food",
        "Cleaning & Household", "Other", "Uncategorized",
    ]
    counts = []
    for cat in categories:
        q = (
            db.table("collective_prices")
            .select("id", count="exact")
            .eq("source", "leaflet")
            .eq("category", cat)
            .execute()
        )
        if q.count and q.count > 0:
            counts.append({"category": cat, "count": q.count})
    counts.sort(key=lambda x: -x["count"])
    total = sum(c["count"] for c in counts)
    return {"categories": counts, "total": total}


@router.get("/products/search")
async def admin_product_search(
    q: str = "",
    store: str = "",
    category: str = "",
    page: int = 1,
    per_page: int = 25,
    _admin: str = Depends(require_admin),
):
    """Search products in collective_prices."""
    db = get_service_client()

    try:
        result = db.rpc("search_products", {
            "search_term": q or None,
            "store_filter": store or None,
            "cat_filter": category or None,
            "page_num": page,
            "page_size": per_page,
        }).execute()

        data = result.data or {}
        if isinstance(data, list) and data:
            data = data[0]

        return {
            "products": data.get("products", []),
            "total": data.get("total", 0),
            "page": page,
            "per_page": per_page,
        }
    except Exception as e:
        log.warning("Product search failed: %s", e)
        return {"products": [], "total": 0, "page": page, "per_page": per_page}


@router.post("/products/{product_id}/category")
async def admin_update_category(
    product_id: str,
    category: str,
    _admin: str = Depends(require_admin),
):
    """Update a product's category."""
    db = get_service_client()
    db.table("collective_prices").update(
        {"category": category}
    ).eq("id", product_id).execute()
    return {"status": "updated", "id": product_id, "category": category}


@router.get("/db/stats")
async def admin_db_stats(_admin: str = Depends(require_admin)):
    """Row counts for key tables."""
    db = get_service_client()
    tables = [
        "profiles", "receipts", "receipt_items", "collective_prices",
        "price_history", "weekly_deals", "shopping_list_items",
        "scraper_runs", "chat_messages",
    ]
    stats = []
    for t in tables:
        try:
            q = db.table(t).select("id", count="exact").execute()
            stats.append({"table": t, "rows": q.count or 0})
        except Exception:
            stats.append({"table": t, "rows": -1})
    return {"tables": stats}


@router.get("/ocr-test")
async def admin_ocr_test(_admin: str = Depends(require_admin)):
    """Test OCR providers — Gemini + OpenAI fallback."""
    results = {}

    # Test Gemini
    try:
        from app.services.ocr_service import _gemini_model
        if _gemini_model is not None:
            response = _gemini_model.generate_content("Respond with only: GEMINI_OK")
            results["gemini"] = {"status": "ok", "response": response.text.strip()[:50]}
        else:
            results["gemini"] = {"status": "unavailable", "response": "Model not loaded"}
    except Exception as e:
        results["gemini"] = {"status": "error", "response": f"{type(e).__name__}: {str(e)[:100]}"}

    # Test OpenAI Vision
    try:
        from app.services.ocr_service import openai_client
        response = await openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": "Respond with only: OPENAI_OK"}],
            max_completion_tokens=10,
        )
        results["openai_vision"] = {"status": "ok", "response": response.choices[0].message.content.strip()[:50]}
    except Exception as e:
        results["openai_vision"] = {"status": "error", "response": f"{type(e).__name__}: {str(e)[:100]}"}

    # Test OpenAI extraction (nano)
    try:
        from openai import AsyncOpenAI
        from app.config import settings
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": "Respond with only: NANO_OK"}],
            max_completion_tokens=10,
        )
        results["openai_nano"] = {"status": "ok", "response": response.choices[0].message.content.strip()[:50]}
    except Exception as e:
        results["openai_nano"] = {"status": "error", "response": f"{type(e).__name__}: {str(e)[:100]}"}

    # Test OpenAI deals (5.4-nano)
    try:
        from openai import AsyncOpenAI
        from app.config import settings
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-5.4-nano",
            messages=[{"role": "user", "content": "Respond with only: GPT54_OK"}],
            max_completion_tokens=10,
        )
        results["openai_5.4_nano"] = {"status": "ok", "response": response.choices[0].message.content.strip()[:50]}
    except Exception as e:
        results["openai_5.4_nano"] = {"status": "error", "response": f"{type(e).__name__}: {str(e)[:100]}"}

    return results


@router.post("/shelf-scan")
async def admin_shelf_scan(
    file: UploadFile = File(...),
    store_name: str = Form(...),
    _admin: str = Depends(require_admin),
):
    """Upload a shelf photo → OCR extracts products → saves to collective_prices."""
    from app.services.ocr_service import extract_shelf_prices
    from app.services.price_service import record_price_history
    from app.utils.text_utils import generate_product_key
    from datetime import timedelta

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    # Extract prices from shelf photo
    products = await extract_shelf_prices(image_bytes)
    if not products:
        return {"status": "no_products", "message": "No prices found in image", "saved": 0}

    db = get_service_client()
    now = datetime.now(timezone.utc)
    saved = 0
    errors = 0

    for p in products:
        product_key = generate_product_key(p["product_name"])
        expires_at = now + timedelta(days=30)  # shelf prices valid ~30 days

        try:
            # Upsert to collective_prices (keeps lower price)
            db.rpc(
                "upsert_collective_price",
                {
                    "p_product_key": product_key,
                    "p_product_name": p["product_name"],
                    "p_category": p["category"],
                    "p_store_name": store_name,
                    "p_store_branch": None,
                    "p_home_area": None,
                    "p_unit_price": p["unit_price"],
                    "p_unit": None,
                    "p_is_on_offer": False,
                    "p_source": "shelf",
                    "p_observed_at": now.isoformat(),
                    "p_expires_at": expires_at.isoformat(),
                },
            ).execute()

            # Record in price history
            await record_price_history(
                db,
                product_key=product_key,
                product_name=p["product_name"],
                store_name=store_name,
                unit_price=p["unit_price"],
                source="shelf",
                observed_at=now,
            )
            saved += 1
        except Exception as e:
            log.warning("Shelf scan: failed to save '%s': %s", p["product_name"], e)
            errors += 1

    return {
        "status": "ok",
        "message": f"Extracted {len(products)} products, saved {saved}",
        "products": products,
        "saved": saved,
        "errors": errors,
    }
