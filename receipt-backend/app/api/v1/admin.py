"""Admin panel API — all routes require is_admin flag on profile."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import get_service_client
from app.utils.auth_utils import get_current_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


async def require_admin(user_id: str = Depends(get_current_user)) -> str:
    """Dependency that ensures the caller has is_admin == True."""
    db = get_service_client()
    row = (
        db.table("profiles")
        .select("is_admin")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if not row.data or not row.data.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


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
    status: str = "ok"


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
        scrapers.append(ScraperInfo(
            name=s["name"],
            schedule=s["schedule"],
            items_count=count_q.count or 0,
            status="ok",
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
    profile = (
        db.table("profiles")
        .select("email, full_name")
        .eq("id", _admin)
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
