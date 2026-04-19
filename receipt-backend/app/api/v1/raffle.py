"""Raffle system — monthly draw with 3 prize tiers.

Users spend points to buy raffle tickets. Each ticket gives a chance
to win one of the monthly prizes. Tickets are unique and serve as
proof of entry.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.database import get_service_client
from app.utils.auth_utils import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/raffle", tags=["raffle"])

# Prize tiers — update these monthly or keep fixed
PRIZES = [
    {
        "tier": 1,
        "name": "Signed Rooney #10 Jersey (Man Utd)",
        "points": 1500,
        "emoji": "🥇",
        "description": "Authentic Manchester United away jersey signed by Wayne Rooney with Beckett certificate",
    },
    {
        "tier": 2,
        "name": "Boots Gift Card €30",
        "points": 1000,
        "emoji": "🥈",
        "description": "€30 gift card for Boots — beauty, skincare, pharmacy and more",
    },
    {
        "tier": 3,
        "name": "One4All Gift Card €30",
        "points": 800,
        "emoji": "🥉",
        "description": "€30 One4All card — accepted at 130+ stores across Ireland",
    },
]


def _current_month() -> str:
    """Return current month as 'YYYY-MM'."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _generate_ticket_number(month: str, count: int) -> str:
    """Generate unique ticket number like SD-MAY26-001."""
    dt = datetime.strptime(month, "%Y-%m")
    month_label = dt.strftime("%b").upper() + dt.strftime("%y")
    return f"SD-{month_label}-{count + 1:03d}"


class EnterRaffleRequest(BaseModel):
    prize_tier: int


@router.get("/prizes")
async def get_prizes(user_id: str = Depends(get_current_user)):
    """Return current month's prizes with user's ticket counts."""
    db = get_service_client()
    month = _current_month()

    # Get user's points
    profile = db.table("profiles").select("points").eq("id", user_id).maybe_single().execute()
    user_points = (profile.data or {}).get("points") or 0

    # Get user's tickets this month
    tickets = (
        db.table("raffle_tickets")
        .select("prize_tier")
        .eq("user_id", user_id)
        .eq("month", month)
        .execute()
    )

    # Count tickets per tier
    tier_counts = {1: 0, 2: 0, 3: 0}
    for t in (tickets.data or []):
        tier = t["prize_tier"]
        if tier in tier_counts:
            tier_counts[tier] += 1

    prizes_with_status = []
    for prize in PRIZES:
        prizes_with_status.append({
            **prize,
            "my_tickets": tier_counts.get(prize["tier"], 0),
            "can_afford": user_points >= prize["points"],
        })

    # Next draw date
    now = datetime.now(timezone.utc)
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1)
    else:
        next_month = now.replace(month=now.month + 1, day=1)
    from datetime import timedelta
    first_sat = next_month
    while first_sat.weekday() != 5:
        first_sat += timedelta(days=1)

    return {
        "month": month,
        "month_label": now.strftime("%B %Y"),
        "prizes": prizes_with_status,
        "user_points": user_points,
        "next_draw": first_sat.strftime("%B %d, %Y"),
    }


@router.post("/enter")
async def enter_raffle(
    body: EnterRaffleRequest,
    user_id: str = Depends(get_current_user),
):
    """Buy a raffle ticket by spending points.

    Deducts points and generates a unique ticket number.
    """
    db = get_service_client()
    month = _current_month()
    tier = body.prize_tier

    # Validate tier
    prize = next((p for p in PRIZES if p["tier"] == tier), None)
    if not prize:
        raise HTTPException(status_code=400, detail="Invalid prize tier")

    # Check user has enough points
    profile = db.table("profiles").select("points").eq("id", user_id).maybe_single().execute()
    if not profile.data:
        raise HTTPException(status_code=404, detail="Profile not found")

    current_points = profile.data.get("points") or 0
    cost = prize["points"]

    if current_points < cost:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough points. You have {current_points} but need {cost}."
        )

    # Count existing tickets this month (for ticket number generation)
    existing = (
        db.table("raffle_tickets")
        .select("id", count="exact")
        .eq("month", month)
        .execute()
    )
    ticket_count = existing.count or 0

    # Generate unique ticket number
    ticket_number = _generate_ticket_number(month, ticket_count)

    # Deduct points + insert ticket (as close together as possible)
    new_points = current_points - cost
    db.table("profiles").update({"points": new_points}).eq("id", user_id).execute()

    try:
        result = db.table("raffle_tickets").insert({
            "user_id": user_id,
            "ticket_number": ticket_number,
            "prize_tier": tier,
            "prize_name": prize["name"],
            "points_spent": cost,
            "month": month,
        }).execute()

        ticket_data = result.data[0] if result.data else {}

        log.info(
            "Raffle ticket sold: user=%s ticket=%s prize=%s cost=%d remaining=%d",
            user_id[:8], ticket_number, prize["name"], cost, new_points,
        )

        return {
            "status": "ok",
            "ticket_number": ticket_number,
            "prize_name": prize["name"],
            "prize_tier": tier,
            "points_spent": cost,
            "points_remaining": new_points,
            "created_at": ticket_data.get("created_at", datetime.now(timezone.utc).isoformat()),
        }

    except Exception as e:
        # Rollback: return points if ticket insert failed
        db.table("profiles").update({"points": current_points}).eq("id", user_id).execute()
        log.error("Raffle ticket insert failed for %s: %s — points refunded", user_id[:8], e)
        raise HTTPException(status_code=500, detail="Could not create ticket. Points refunded.")


@router.get("/my-tickets")
async def my_tickets(
    month: str | None = Query(None, description="Month in YYYY-MM format"),
    user_id: str = Depends(get_current_user),
):
    """List user's raffle tickets for a given month (defaults to current)."""
    db = get_service_client()
    target_month = month or _current_month()

    tickets = (
        db.table("raffle_tickets")
        .select("*")
        .eq("user_id", user_id)
        .eq("month", target_month)
        .order("created_at", desc=True)
        .execute()
    )

    return {
        "month": target_month,
        "tickets": tickets.data or [],
        "total_tickets": len(tickets.data or []),
    }
