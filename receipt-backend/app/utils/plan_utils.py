"""Free vs Pro plan enforcement utilities."""

from datetime import date, datetime, timezone

from fastapi import HTTPException

FREE_SCANS_PER_MONTH = 10
FREE_CHAT_QUERIES_PER_DAY = 5


def is_pro(profile: dict) -> bool:
    """Return True if the user has an active Pro plan."""
    if profile.get("plan") != "pro":
        return False
    expires = profile.get("plan_expires_at")
    if not expires:
        return False
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires > datetime.now(timezone.utc)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _this_month() -> date:
    return _today().replace(day=1)


def check_scan_limit(db, user_id: str, profile: dict) -> None:  # noqa: ANN001
    """Raise 402 if free user exceeded monthly scan limit."""
    if is_pro(profile):
        return

    # Reset counter if month changed
    reset_raw = profile.get("scans_month_reset")
    if reset_raw:
        reset_date = (
            date.fromisoformat(reset_raw)
            if isinstance(reset_raw, str)
            else reset_raw
        )
        if reset_date < _this_month():
            db.table("profiles").update({
                "scans_this_month": 0,
                "scans_month_reset": _this_month().isoformat(),
            }).eq("id", user_id).execute()
            return  # counter was just reset — allow

    count = profile.get("scans_this_month") or 0
    if count >= FREE_SCANS_PER_MONTH:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Free plan limit: {FREE_SCANS_PER_MONTH} scans/month. "
                "Upgrade to Pro for unlimited scans."
            ),
        )


def check_chat_limit(db, user_id: str, profile: dict) -> None:  # noqa: ANN001
    """Raise 402 if free user exceeded daily chat query limit."""
    if is_pro(profile):
        return

    reset_raw = profile.get("chat_queries_reset")
    if reset_raw:
        reset_date = (
            date.fromisoformat(reset_raw)
            if isinstance(reset_raw, str)
            else reset_raw
        )
        if reset_date < _today():
            db.table("profiles").update({
                "chat_queries_today": 0,
                "chat_queries_reset": _today().isoformat(),
            }).eq("id", user_id).execute()
            return

    count = profile.get("chat_queries_today") or 0
    if count >= FREE_CHAT_QUERIES_PER_DAY:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Free plan limit: {FREE_CHAT_QUERIES_PER_DAY} AI queries/day. "
                "Upgrade to Pro for unlimited chat."
            ),
        )


def increment_scan_count(db, user_id: str) -> None:  # noqa: ANN001
    """Increment the monthly scan counter. Awards Pro monthly bonus (+200 pts) on first scan of new month."""
    import logging
    _log = logging.getLogger(__name__)

    today = _this_month()
    profile = (
        db.table("profiles")
        .select("scans_this_month, scans_month_reset, points, plan, plan_expires_at")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    data = profile.data or {}
    current = data.get("scans_this_month") or 0
    month_just_reset = False

    reset_raw = data.get("scans_month_reset")
    if reset_raw:
        reset_date = (
            date.fromisoformat(reset_raw)
            if isinstance(reset_raw, str)
            else reset_raw
        )
        if reset_date < today:
            current = 0
            month_just_reset = True

    update_fields = {
        "scans_this_month": current + 1,
        "scans_month_reset": today.isoformat(),
    }

    # Pro monthly bonus: +200 pts on first scan of a new month
    if month_just_reset and is_pro(data):
        current_pts = data.get("points") or 0
        update_fields["points"] = current_pts + 200
        _log.info("Pro monthly bonus: +200 pts for user %s", user_id[:8])

    db.table("profiles").update(update_fields).eq("id", user_id).execute()


def increment_chat_count(db, user_id: str) -> None:  # noqa: ANN001
    """Increment the daily chat query counter."""
    today = _today()
    profile = (
        db.table("profiles")
        .select("chat_queries_today, chat_queries_reset")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    data = profile.data or {}
    current = data.get("chat_queries_today") or 0

    reset_raw = data.get("chat_queries_reset")
    if reset_raw:
        reset_date = (
            date.fromisoformat(reset_raw)
            if isinstance(reset_raw, str)
            else reset_raw
        )
        if reset_date < today:
            current = 0

    db.table("profiles").update({
        "chat_queries_today": current + 1,
        "chat_queries_reset": today.isoformat(),
    }).eq("id", user_id).execute()
