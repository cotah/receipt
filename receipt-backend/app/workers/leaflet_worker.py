import asyncio
import json as _json
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from app.config import settings
from app.database import get_service_client
from app.utils.text_utils import generate_product_key

log = logging.getLogger(__name__)

try:
    from curl_cffi.requests import AsyncSession as CurlSession  # noqa: F401

    _CURL_CFFI_AVAILABLE = True
except ImportError:
    _CURL_CFFI_AVAILABLE = False
    log.warning(
        "curl-cffi not installed — Dunnes TLS impersonation unavailable"
    )

PAGE_SIZE = 30

# ---------------------------------------------------------------------------
# User-Agent rotation pool
# ---------------------------------------------------------------------------

USER_AGENTS = [
    # Chrome 131 — Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    # Chrome 131 — macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    # Firefox 133 — Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) "
        "Gecko/20100101 Firefox/133.0"
    ),
    # Safari 17 — macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Safari/605.1.15"
    ),
    # Edge 131 — Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
    ),
]


def _random_headers(
    *,
    referer: str | None = None,
    origin: str | None = None,
    accept: str | None = None,
) -> dict[str, str]:
    """Build browser-like headers with a random User-Agent."""
    ua = random.choice(USER_AGENTS)
    h: dict[str, str] = {
        "User-Agent": ua,
        "Accept": accept or (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-IE,en-GB;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    if referer:
        h["Referer"] = referer
    if origin:
        h["Origin"] = origin
    return h


async def _page_delay() -> None:
    """Random delay between page requests (3–8 s)."""
    await asyncio.sleep(random.uniform(3, 8))


async def _short_delay() -> None:
    """Short random delay (0.5–1.5 s)."""
    await asyncio.sleep(random.uniform(0.5, 1.5))


async def _startup_delay() -> None:
    """Random delay before starting a scraper (1–3 s)."""
    await asyncio.sleep(random.uniform(1, 3))


# ---------------------------------------------------------------------------
# Proxy / Apify / Run tracking / Auto-Fix AI helpers
# ---------------------------------------------------------------------------


def _make_client_kwargs(*, use_proxy: bool = False) -> dict:
    """Return kwargs for httpx.AsyncClient, optionally with Webshare proxy."""
    kwargs: dict = {
        "timeout": 45,
        "follow_redirects": True,
    }
    if use_proxy and settings.WEBSHARE_PROXY_URL:
        kwargs["proxies"] = {
            "http://": settings.WEBSHARE_PROXY_URL,
            "https://": settings.WEBSHARE_PROXY_URL,
        }
    return kwargs


async def _run_apify_actor(
    actor_id: str,
    run_input: dict,
    timeout_secs: int = 2400,
    poll_interval: int = 30,
    max_dataset_age_hours: int = 24,
) -> list[dict]:
    """Run an Apify actor and return dataset items. Empty list on failure.

    Strategy (smart reuse):
    1. Check recent runs (last 24h) — if one SUCCEEDED with data, reuse it
    2. Check if a run is already RUNNING — wait for it instead of starting new
    3. Only start a NEW run if no recent data and nothing running
    4. Poll until complete, then fetch dataset items via JSON API
    """
    token = settings.APIFY_API_TOKEN
    if not token or not actor_id:
        log.info("Apify: token or actor_id not configured — skipping")
        return []

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            # ── Step 1: Check recent runs for reusable data ──
            best_ds_id = None
            best_ds_count = 0
            running_run_id = None
            running_ds_id = None
            try:
                runs_resp = await client.get(
                    f"https://api.apify.com/v2/acts/{actor_id}/runs",
                    params={
                        "token": token,
                        "limit": 5,
                        "desc": "true",
                    },
                )
                if runs_resp.status_code == 200:
                    recent_runs = (
                        runs_resp.json()
                        .get("data", {})
                        .get("items", [])
                    )

                    # Find the BEST dataset (most items) among
                    # recent SUCCEEDED runs
                    for prev_run in recent_runs:
                        if prev_run.get("status") == "RUNNING":
                            if not running_run_id:
                                running_run_id = prev_run.get("id")
                                running_ds_id = prev_run.get(
                                    "defaultDatasetId"
                                )
                            continue

                        if prev_run.get("status") != "SUCCEEDED":
                            continue
                        ds_id = prev_run.get("defaultDatasetId")
                        if not ds_id:
                            continue

                        # Check age
                        finished = prev_run.get("finishedAt", "")
                        if finished:
                            from datetime import datetime, timezone
                            try:
                                fin_dt = datetime.fromisoformat(
                                    finished.replace("Z", "+00:00")
                                )
                                age_h = (
                                    datetime.now(timezone.utc) - fin_dt
                                ).total_seconds() / 3600
                                if age_h > max_dataset_age_hours:
                                    continue
                            except Exception:
                                pass

                        # Check dataset item count
                        try:
                            ds_resp = await client.get(
                                f"https://api.apify.com/v2/"
                                f"datasets/{ds_id}",
                                params={"token": token},
                            )
                            if ds_resp.status_code == 200:
                                item_count = (
                                    ds_resp.json()
                                    .get("data", {})
                                    .get("itemCount", 0)
                                )
                                if item_count > best_ds_count:
                                    best_ds_count = item_count
                                    best_ds_id = ds_id
                        except Exception:
                            pass

                    # Use the best dataset if found
                    if best_ds_id and best_ds_count > 0:
                        log.info(
                            "Apify: reusing best recent dataset %s "
                            "(%d items)",
                            best_ds_id,
                            best_ds_count,
                        )
                        return await _fetch_apify_dataset(
                            client, token, actor_id, best_ds_id
                        )

                    # Or wait for a running run
                    if running_run_id and running_ds_id:
                        log.info(
                            "Apify: actor %s already running "
                            "(run=%s) — waiting for it",
                            actor_id,
                            running_run_id,
                        )
                        return await _wait_and_fetch_apify(
                            client, token, actor_id,
                            running_run_id, running_ds_id,
                            timeout_secs, poll_interval,
                        )
            except Exception as e:
                log.warning(
                    "Apify: error checking recent runs: %s", e
                )

            # ── Step 2: No recent data — start a new run ──
            log.info(
                "Apify: no recent data found — starting new run "
                "for actor %s",
                actor_id,
            )
            run_resp = await client.post(
                f"https://api.apify.com/v2/acts/{actor_id}/runs",
                params={"token": token},
                json=run_input,
            )
            if run_resp.status_code not in (200, 201):
                log.warning(
                    "Apify: actor %s start returned %d",
                    actor_id,
                    run_resp.status_code,
                )
                return []

            run_data = run_resp.json().get("data", {})
            run_id = run_data.get("id")
            dataset_id = run_data.get("defaultDatasetId")
            if not run_id or not dataset_id:
                log.warning("Apify: no run_id or datasetId in response")
                return []

            log.info(
                "Apify: actor %s started (run=%s, dataset=%s)",
                actor_id,
                run_id,
                dataset_id,
            )

            return await _wait_and_fetch_apify(
                client, token, actor_id,
                run_id, dataset_id,
                timeout_secs, poll_interval,
            )

    except Exception as e:
        log.error("Apify: error running actor %s: %s", actor_id, e)
        return []


async def _wait_and_fetch_apify(
    client, token, actor_id, run_id, dataset_id,
    timeout_secs, poll_interval,
) -> list[dict]:
    """Poll an Apify run until complete, then fetch dataset items."""
    elapsed = 0
    while elapsed < timeout_secs:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        try:
            status_resp = await client.get(
                f"https://api.apify.com/v2/actor-runs/{run_id}",
                params={"token": token},
            )
            if status_resp.status_code != 200:
                continue
            run_status = (
                status_resp.json()
                .get("data", {})
                .get("status", "RUNNING")
            )
        except Exception:
            continue

        if run_status in (
            "SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"
        ):
            log.info(
                "Apify: actor %s finished status=%s after %ds",
                actor_id,
                run_status,
                elapsed,
            )
            break

        if elapsed % 120 == 0:
            log.info(
                "Apify: actor %s still running (%ds elapsed)",
                actor_id,
                elapsed,
            )

    return await _fetch_apify_dataset(
        client, token, actor_id, dataset_id
    )


async def _fetch_apify_dataset(
    client, token, actor_id, dataset_id,
) -> list[dict]:
    """Fetch all items from an Apify dataset via JSON API."""
    items_resp = await client.get(
        f"https://api.apify.com/v2/datasets/{dataset_id}/items",
        params={"token": token, "format": "json"},
    )
    if items_resp.status_code != 200:
        log.warning(
            "Apify: dataset %s returned %d",
            dataset_id,
            items_resp.status_code,
        )
        return []

    items = items_resp.json() or []
    log.info(
        "Apify: actor %s dataset %s returned %d items",
        actor_id,
        dataset_id,
        len(items),
    )
    return items


def _start_run(db, store_name: str) -> str | None:
    """Insert a scraper_runs record. Returns the id or None."""
    try:
        result = (
            db.table("scraper_runs")
            .insert(
                {
                    "store_name": store_name,
                    "status": "running",
                    "fallback_level": 0,
                }
            )
            .execute()
        )
        return result.data[0]["id"] if result.data else None
    except Exception as e:
        log.warning("_start_run [%s]: %s", store_name, e)
        return None


def _finish_run(
    db,
    run_id: str | None,
    *,
    status: str,
    fallback_level: int,
    items_saved: int,
    error_detail: str | None = None,
    autofix_confidence: float | None = None,
    autofix_applied: bool = False,
) -> None:
    """Update the scraper_runs record. Never crashes."""
    if not run_id:
        return
    try:
        db.table("scraper_runs").update(
            {
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "fallback_level": fallback_level,
                "items_saved": items_saved,
                "error_detail": error_detail,
                "autofix_confidence": autofix_confidence,
                "autofix_applied": autofix_applied,
            }
        ).eq("id", run_id).execute()
    except Exception as e:
        log.warning("_finish_run [%s]: %s", run_id, e)


def _get_checkpoint(db, store_name: str) -> dict | None:
    """Read saved checkpoint. None if not found."""
    try:
        r = (
            db.table("scraper_checkpoints")
            .select("*")
            .eq("store_name", store_name)
            .limit(1)
            .execute()
        )
        return r.data[0] if r.data else None
    except Exception:
        return None


def _save_checkpoint(
    db, store_name: str, page: int, items: int
) -> None:
    """Save/update checkpoint every N pages. Never crashes."""
    try:
        db.table("scraper_checkpoints").upsert(
            {
                "store_name": store_name,
                "last_page": page,
                "items_saved": items,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
    except Exception:
        pass


def _clear_checkpoint(db, store_name: str) -> None:
    """Delete checkpoint when scraper finishes successfully. Never crashes."""
    try:
        db.table("scraper_checkpoints").delete().eq(
            "store_name", store_name
        ).execute()
    except Exception:
        pass


async def _autofix_scraper_ai(
    store_name: str,
    error_context: str,
    sample_html: str = "",
) -> tuple[float, str | None]:
    """GPT analyses the error and proposes a fix. Only acts at >= 80%."""
    if not settings.OPENAI_API_KEY:
        return 0.0, None

    from openai import AsyncOpenAI

    ai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    prompt = f"""You are a senior Python developer debugging a web scraper \
for {store_name} Ireland.

Error context:
{error_context}

Sample HTML (first 2000 chars):
{sample_html[:2000] if sample_html else "Not available"}

Analyse the error and respond ONLY with valid JSON:
{{
  "confidence": 0.85,
  "diagnosis": "Short description of what broke",
  "fix_type": "endpoint_change | location_id | headers | auth | other",
  "proposed_fix": "What should change in the code",
  "risk": "low | medium | high",
  "can_auto_apply": true
}}

Rules:
- confidence: 0.0 to 1.0
- can_auto_apply=true only if confidence >= 0.8 AND risk == "low"
- Be conservative — prefer lower confidence over wrong fixes
"""

    try:
        response = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=400,
        )
        data = _json.loads(response.choices[0].message.content or "{}")
        confidence = float(data.get("confidence", 0.0))
        diagnosis = data.get("diagnosis", "unknown")
        can_auto_apply = data.get("can_auto_apply", False)
        proposed_fix = data.get("proposed_fix", "")

        try:
            import sentry_sdk

            sentry_sdk.capture_message(
                f"[AutoFix AI] {store_name}: {confidence:.0%} — {diagnosis}",
                level="warning" if confidence < 0.8 else "info",
                tags={
                    "scraper": store_name.lower(),
                    "autofix_confidence": str(round(confidence, 2)),
                    "can_auto_apply": str(can_auto_apply),
                },
            )
        except Exception:
            pass

        log.info(
            "AutoFix AI [%s]: confidence=%.0f%%, can_apply=%s — %s",
            store_name,
            confidence * 100,
            can_auto_apply,
            diagnosis,
        )

        if confidence >= 0.8 and can_auto_apply:
            return confidence, proposed_fix
        else:
            log.warning(
                "AutoFix AI [%s]: confidence %.0f%% insufficient "
                "or high risk — alerting only",
                store_name,
                confidence * 100,
            )
            return confidence, None

    except Exception as e:
        log.error("AutoFix AI [%s]: failed — %s", store_name, e)
        return 0.0, None


# ---------------------------------------------------------------------------
# Mi9 store configurations
# ---------------------------------------------------------------------------


class Mi9Store(NamedTuple):
    store_name: str
    session_url: str
    api_base: str
    location_id: str | None  # None = discover at runtime
    total_pages: int
    referer: str
    origin: str


DUNNES = Mi9Store(
    store_name="Dunnes",
    session_url=(
        "https://www.dunnesstoresgrocery.com"
        "/sm/delivery/rsid/258/promotions"
    ),
    api_base=(
        "https://storefrontgateway.dunnesstoresgrocery.com"
        "/api/stores/258/locations"
    ),
    location_id="5df95c07-402e-419a-a699-8b895311ac5a",
    total_pages=215,
    referer=(
        "https://www.dunnesstoresgrocery.com"
        "/sm/delivery/rsid/258/promotions"
    ),
    origin="https://www.dunnesstoresgrocery.com",
)

SUPERVALU = Mi9Store(
    store_name="SuperValu",
    session_url=(
        "https://shop.supervalu.ie"
        "/sm/delivery/rsid/5550/promotions"
    ),
    api_base=(
        "https://storefrontgateway.supervalu.ie"
        "/api/stores/5550/locations"
    ),
    location_id=None,  # discover at runtime via _discover_location_id()
    total_pages=121,
    referer=(
        "https://shop.supervalu.ie"
        "/sm/delivery/rsid/5550/promotions"
    ),
    origin="https://shop.supervalu.ie",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_expires(item: dict, fallback: datetime) -> datetime:
    """Extract expiry from promotions[0].endDateUtc, or use fallback."""
    promotions = item.get("promotions")
    if promotions and len(promotions) > 0:
        end_str = promotions[0].get("endDateUtc")
        if end_str:
            try:
                dt = dateutil_parser.isoparse(end_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError):
                pass
    return fallback


_LOCATION_RE = re.compile(
    r"/locations/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}"
    r"-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


async def _discover_location_id(
    client: httpx.AsyncClient,
    session_resp: httpx.Response,
    store: Mi9Store,
) -> str | None:
    """Extract Mi9 location UUID from the session response URL chain or
    store-info API.  Does NOT use client.history (httpx doesn't have it)."""

    # 1. Check the final URL after redirects
    m = _LOCATION_RE.search(str(session_resp.url))
    if m:
        return m.group(1)

    # 2. Check response body for location references
    try:
        body = session_resp.text
        m = _LOCATION_RE.search(body)
        if m:
            return m.group(1)
    except Exception:
        pass

    # 3. Try the store-info endpoint
    try:
        await _short_delay()
        info_resp = await client.get(
            f"{store.api_base.rsplit('/locations', 1)[0]}/info",
        )
        if info_resp.status_code == 200:
            info = info_resp.json()
            loc_id = info.get("locationId") or info.get("location_id")
            if loc_id:
                return loc_id
    except Exception:
        pass

    # Alert via Sentry when discovery fails
    try:
        import sentry_sdk

        sentry_sdk.capture_message(
            f"{store.store_name} scraper: location_id discovery failed",
            level="error",
            tags={
                "scraper": store.store_name.lower(),
                "error": "location_id_not_found",
            },
        )
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Mi9 item saver (extracted for reuse by Apify fallback)
# ---------------------------------------------------------------------------


async def _save_mi9_items(
    db,
    store: Mi9Store,
    products: list,
    now: datetime | None = None,
    default_expires: datetime | None = None,
) -> int:
    """Save Mi9 items to collective_prices. Returns count saved."""
    if now is None:
        now = datetime.now(timezone.utc)
    if default_expires is None:
        default_expires = now + timedelta(days=7)

    count = 0
    for item in products:
        try:
            name = item.get("name")
            price = item.get("priceNumeric")
            if not name or price is None:
                continue

            promo_name = None
            promotions = item.get("promotions")
            if promotions:
                promo_name = promotions[0].get("name")

            categories = item.get("defaultCategory", [])
            category = (
                categories[0].get("category", "Other") if categories else "Other"
            )
            expires_at = _parse_expires(item, default_expires)
            product_key = generate_product_key(name)

            db.table("collective_prices").upsert(
                {
                    "product_key": product_key,
                    "product_name": name,
                    "category": category,
                    "store_name": store.store_name,
                    "unit_price": float(price),
                    "is_on_offer": promo_name is not None,
                    "source": "leaflet",
                    "observed_at": now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                },
                on_conflict="product_key,store_name,source",
            ).execute()
            count += 1
        except Exception as e:
            log.warning(
                "_save_mi9_items [%s]: item error: %s", store.store_name, e
            )
    return count


# ---------------------------------------------------------------------------
# Mi9 single attempt (direct or proxy)
# ---------------------------------------------------------------------------


async def _scrape_mi9_attempt(
    store: Mi9Store,
    db,
    use_proxy: bool = False,
) -> dict:
    """One scrape attempt (direct or via Webshare proxy).
    Returns {"success": bool, "items_saved": int, "error": str|None}."""
    now = datetime.now(timezone.utc)
    default_expires = now + timedelta(days=7)
    total_saved = 0
    mode = "proxy" if use_proxy else "direct"
    label = f"{store.store_name}({mode})"

    headers = _random_headers(referer=store.referer, origin=store.origin)
    client_kwargs = _make_client_kwargs(use_proxy=use_proxy)
    client_kwargs["headers"] = headers

    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            # Session with retry
            session_resp = None
            for attempt in range(1, 4):
                try:
                    resp = await client.get(store.session_url)
                    if resp.status_code == 403:
                        log.warning(
                            "%s: 403 on session (attempt %d/3)",
                            label,
                            attempt,
                        )
                        await asyncio.sleep(random.uniform(5, 10))
                        client.headers["User-Agent"] = random.choice(
                            USER_AGENTS
                        )
                        continue
                    resp.raise_for_status()
                    session_resp = resp
                    break
                except httpx.HTTPStatusError:
                    if attempt == 3:
                        return {
                            "success": False,
                            "items_saved": 0,
                            "error": "Session failed after 3 attempts",
                        }
                    await asyncio.sleep(random.uniform(5, 10))
                except Exception as e:
                    return {
                        "success": False,
                        "items_saved": 0,
                        "error": str(e),
                    }

            if session_resp is None:
                return {
                    "success": False,
                    "items_saved": 0,
                    "error": "No session response",
                }

            log.info(
                "%s: session OK (%d cookies)", label, len(client.cookies)
            )

            # Resolve location_id
            location_id = store.location_id
            if location_id is None:
                location_id = await _discover_location_id(
                    client, session_resp, store
                )
                if location_id is None:
                    return {
                        "success": False,
                        "items_saved": 0,
                        "error": "location_id not discovered",
                    }
                log.info("%s: location_id=%s", label, location_id)

            api_url = (
                f"{store.api_base}/{location_id}/aisle/page_promotion"
            )

            client.headers["Accept"] = (
                "application/json, text/plain, */*"
            )
            client.headers["Sec-Fetch-Dest"] = "empty"
            client.headers["Sec-Fetch-Mode"] = "cors"
            client.headers["Sec-Fetch-Site"] = "same-site"

            consecutive_403 = 0
            for page in range(1, store.total_pages + 1):
                skip = (page - 1) * PAGE_SIZE
                params = {
                    "page": page,
                    "skip": skip,
                    "pageSize": PAGE_SIZE,
                }

                try:
                    resp = await client.get(api_url, params=params)
                    if resp.status_code == 403:
                        consecutive_403 += 1
                        log.warning(
                            "%s: 403 on page %d (%d consecutive)",
                            label,
                            page,
                            consecutive_403,
                        )
                        if consecutive_403 >= 3:
                            log.warning(
                                "%s: 3 consecutive 403s — stopping",
                                label,
                            )
                            break
                        await asyncio.sleep(random.uniform(8, 15))
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    consecutive_403 = 0
                except Exception as e:
                    log.warning(
                        "%s: page %d failed: %s", label, page, e
                    )
                    await _page_delay()
                    continue

                products = (
                    data
                    if isinstance(data, list)
                    else data.get("products", data.get("items", []))
                )

                saved = await _save_mi9_items(
                    db, store, products, now, default_expires
                )
                total_saved += saved

                if page % 50 == 0:
                    log.info(
                        "%s: %d/%d pages (%d items)",
                        label,
                        page,
                        store.total_pages,
                        total_saved,
                    )

                await _page_delay()

        if total_saved > 0:
            return {
                "success": True,
                "items_saved": total_saved,
                "error": None,
            }
        else:
            return {
                "success": False,
                "items_saved": 0,
                "error": "Zero items saved — possible block",
            }

    except Exception as e:
        return {"success": False, "items_saved": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# Generic Mi9 scraper with fallback chain (Dunnes, SuperValu)
# ---------------------------------------------------------------------------


async def scrape_mi9_store(store: Mi9Store) -> None:
    """Scrape Mi9 with fallback chain:
    0 -> direct, 1 -> Webshare proxy, 2 -> Apify, 3 -> Auto-Fix AI."""
    db = get_service_client()
    run_id = _start_run(db, store.store_name)
    label = f"{store.store_name} scraper"

    log.info("%s: starting with fallback chain...", label)
    await _startup_delay()

    # Fallback 0: direct
    result = await _scrape_mi9_attempt(store, db, use_proxy=False)
    if result["success"]:
        _finish_run(
            db, run_id, status="success", fallback_level=0,
            items_saved=result["items_saved"],
        )
        log.info(
            "%s: success direct (%d items)", label, result["items_saved"]
        )
        return
    log.warning("%s: fallback 0 failed — %s", label, result.get("error"))

    # Fallback 1: Webshare proxy
    if not settings.WEBSHARE_PROXY_URL:
        log.info("%s: WEBSHARE_PROXY_URL not set — skipping fallback 1", label)
    else:
        log.info("%s: trying via Webshare proxy...", label)
        result = await _scrape_mi9_attempt(store, db, use_proxy=True)
        if result["success"]:
            _finish_run(
                db, run_id, status="success", fallback_level=1,
                items_saved=result["items_saved"],
            )
            log.info(
                "%s: success via proxy (%d items)",
                label,
                result["items_saved"],
            )
            return
        log.warning(
            "%s: fallback 1 failed — %s", label, result.get("error")
        )

    # Fallback 2: Apify
    actor_id = (
        settings.APIFY_ACTOR_DUNNES
        if store.store_name == "Dunnes"
        else settings.APIFY_ACTOR_SUPERVALU
    )
    if actor_id and settings.APIFY_API_TOKEN:
        log.info("%s: trying Apify actor %s...", label, actor_id)
        items = await _run_apify_actor(
            actor_id,
            {"startUrls": [{"url": store.session_url}]},
        )
        if items:
            saved = await _save_mi9_items(db, store, items)
            _finish_run(
                db, run_id, status="success", fallback_level=2,
                items_saved=saved,
            )
            log.info("%s: success via Apify (%d items)", label, saved)
            return
        log.warning("%s: fallback 2 (Apify) returned 0 items", label)
    else:
        log.info(
            "%s: Apify not configured for this scraper — skipping", label
        )

    # Fallback 3: Auto-Fix AI
    log.error(
        "%s: all fallbacks failed — activating Auto-Fix AI", label
    )
    error_ctx = (
        f"Store: {store.store_name}, "
        f"session_url: {store.session_url}, "
        f"api_base: {store.api_base}, "
        f"last_error: {result.get('error', 'unknown')}"
    )
    confidence, fix = await _autofix_scraper_ai(
        store.store_name, error_ctx
    )

    _finish_run(
        db, run_id,
        status="failed",
        fallback_level=3,
        items_saved=0,
        error_detail=(
            f"All fallbacks failed. AutoFix: {confidence:.0%} confidence"
        ),
        autofix_confidence=confidence,
        autofix_applied=fix is not None,
    )
    log.error("%s: failed at all levels", label)


# ---------------------------------------------------------------------------
# Lidl Ireland (Schwarz API) scraper
# ---------------------------------------------------------------------------

LIDL_FLYER_API = "https://endpoints.leaflets.schwarz/v4/flyer"

_MONTH_NAMES = [
    "",
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]


def _lidl_flyer_slug(today: datetime | None = None) -> str:
    """Build the Lidl flyer slug for the current active week.

    Format: ``from-thu-DD-MM-to-wed-DD-MM-{month(s)}``
    Thursday is the MOST RECENT Thursday (inclusive of today if Thursday).
    Wednesday is 6 days after that Thursday.
    """
    if today is None:
        today = datetime.now(timezone.utc)

    # Most recent Thursday (the active flyer started then).
    # weekday(): Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    # days_since_thu=0 when today IS Thursday → use today
    days_since_thu = (today.weekday() - 3) % 7
    thu = today - timedelta(days=days_since_thu)
    wed = thu + timedelta(days=6)

    thu_dd = f"{thu.day:02d}"
    thu_mm = f"{thu.month:02d}"
    wed_dd = f"{wed.day:02d}"
    wed_mm = f"{wed.month:02d}"

    if thu.month == wed.month:
        suffix = _MONTH_NAMES[thu.month]
    else:
        suffix = (
            f"{_MONTH_NAMES[thu.month]}-to-{_MONTH_NAMES[wed.month]}"
        )

    return (
        f"from-thu-{thu_dd}-{thu_mm}-to-wed-{wed_dd}-{wed_mm}"
        f"-{suffix}"
    )


async def scrape_lidl_leaflet() -> None:
    """Fetch the current Lidl Ireland weekly flyer via Schwarz API structured data.

    Uses pages[].links[] from the API (real product data), NOT PDF OCR.
    For each product, fetches the price from the lidl.ie product page.
    """
    db = get_service_client()
    run_id = _start_run(db, "Lidl")
    now = datetime.now(timezone.utc)
    default_expires = now + timedelta(days=7)
    total_saved = 0
    skipped = 0
    errors = 0

    slug = _lidl_flyer_slug(now)
    log.info("Lidl scraper: slug=%s", slug)
    await _startup_delay()

    headers = _random_headers()
    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers=headers,
    ) as client:
        params = {
            "flyer_identifier": slug,
            "region_id": "0",
            "region_code": "0",
        }
        try:
            resp = await client.get(LIDL_FLYER_API, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.error("Lidl scraper: API request failed: %s", e)
            _finish_run(
                db, run_id, status="failed", fallback_level=0,
                items_saved=0,
                error_detail=f"Schwarz API request failed: {e}",
            )
            return

        # Parse flyer end date for expiry
        flyer_end = default_expires
        flyer_info = data if isinstance(data, dict) else {}
        end_str = (
            flyer_info.get("endDate") or flyer_info.get("end_date")
        )
        if end_str:
            try:
                dt = dateutil_parser.isoparse(end_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                flyer_end = dt
            except (ValueError, TypeError):
                pass

        # Extract products from structured API data: pages[].links[]
        flyer_data = data.get("flyer", data)
        pages = flyer_data.get("pages", [])

        product_links: list[dict] = []
        for pg in pages:
            for link in pg.get("links", []):
                if link.get("displayType") == "product":
                    pd = link.get("productDetails", {})
                    title = (
                        link.get("title")
                        or pd.get("title", "")
                    )
                    product_id = pd.get("productId", "")
                    url = link.get("url", "")
                    # Try to get price directly from API data
                    price_raw = (
                        pd.get("price")
                        or pd.get("currentPrice")
                        or link.get("price")
                    )
                    if title:
                        product_links.append({
                            "title": title.strip(),
                            "productId": product_id,
                            "url": url,
                            "api_price": price_raw,
                        })

        # Deduplicate by productId
        seen: set[str] = set()
        unique_links: list[dict] = []
        for lnk in product_links:
            key = lnk["productId"] or lnk["title"]
            if key and key not in seen:
                seen.add(key)
                unique_links.append(lnk)

        log.info(
            "Lidl scraper: found %d unique products in API data",
            len(unique_links),
        )

        if not unique_links:
            _finish_run(
                db, run_id, status="failed", fallback_level=0,
                items_saved=0,
                error_detail=(
                    f"Zero products in API response (slug={slug}). "
                    f"Pages: {len(pages)}"
                ),
            )
            return

        # Fetch prices from product pages (batched)
        async def _fetch_lidl_price(http_client, lnk):
            """Fetch price for a Lidl product from its web page."""
            # If API had a price, use it directly
            if lnk.get("api_price") is not None:
                try:
                    return {
                        "title": lnk["title"],
                        "price": float(lnk["api_price"]),
                    }
                except (ValueError, TypeError):
                    pass

            # Otherwise fetch from product URL
            try:
                url = (
                    lnk["url"]
                    or f"https://www.lidl.ie/p/p{lnk['productId']}"
                )
                if not url.startswith("http"):
                    url = f"https://www.lidl.ie{url}"
                r = await http_client.get(url, timeout=15)
                if r.status_code != 200:
                    return None
                prices_found = re.findall(
                    r"€\s*([\d]+\.[\d]{2})", r.text
                )
                if not prices_found:
                    return None
                price = float(min(prices_found, key=float))
                return {"title": lnk["title"], "price": price}
            except Exception as e:
                log.debug(
                    "Lidl price fetch failed for %s: %s",
                    lnk.get("productId"),
                    e,
                )
                return None

        # Fetch prices in batches of 10
        products: list[dict] = []
        batch_size = 10
        for i in range(0, len(unique_links), batch_size):
            batch = unique_links[i: i + batch_size]
            results = await asyncio.gather(
                *[_fetch_lidl_price(client, lnk) for lnk in batch]
            )
            products.extend([r for r in results if r])
            await asyncio.sleep(0.5)

        log.info(
            "Lidl scraper: got prices for %d/%d products",
            len(products),
            len(unique_links),
        )

        # Save to collective_prices (grocery items only)
        # Lidl leaflets include tools, clothes, toys etc — filter those out
        _LIDL_NON_GROCERY_BRANDS = {
            "parkside", "silvercrest", "crivit", "esmara", "livergy",
            "ernesto", "florabest", "livarno", "melinera", "auriol",
            "sanitas", "ideenwelt", "powerfix", "ultimate speed",
        }
        _LIDL_NON_GROCERY_KEYWORDS = {
            "chainsaw", "lawnmower", "pressure washer", "hedge trimmer",
            "pruner", "pruning saw", "cable reel", "hose reel",
            "hose", "work trousers", "work gloves", "cargo",
            "hoodie", "sweatshorts", "t-shirt", "joggers", "leggings",
            "sneakers", "clogs", "slippers", "pyjamas",
            "puzzle", "stationery", "soft toy", "nanofigures",
            "lego", "minecraft", "super mario", "zuru",
            "induction hob", "microwave", "toaster", "kettle",
            "vacuum sealer", "sealing clips",
            "frying pan", "knife assortment",
            "grass trimmer", "combi-shear", "pole pruner",
        }

        for item in products:
            try:
                name = item["title"]
                price = item["price"]
                if not name or price is None or price <= 0:
                    continue

                # Filter non-grocery items
                name_lower = name.lower()
                is_non_grocery = False
                for brand in _LIDL_NON_GROCERY_BRANDS:
                    if brand in name_lower:
                        is_non_grocery = True
                        break
                if not is_non_grocery:
                    for kw in _LIDL_NON_GROCERY_KEYWORDS:
                        if kw in name_lower:
                            is_non_grocery = True
                            break
                if is_non_grocery:
                    skipped += 1
                    continue

                product_key = generate_product_key(name)

                db.table("collective_prices").upsert(
                    {
                        "product_key": product_key,
                        "product_name": name,
                        "category": "Other",
                        "store_name": "Lidl",
                        "unit_price": price,
                        "is_on_offer": True,
                        "source": "leaflet",
                        "observed_at": now.isoformat(),
                        "expires_at": flyer_end.isoformat(),
                    },
                    on_conflict="product_key,store_name,source",
                ).execute()
                total_saved += 1
            except Exception as e:
                errors += 1
                log.warning("Lidl scraper: item error: %s", e)

    _finish_run(
        db, run_id,
        status="success" if total_saved > 0 else "failed",
        fallback_level=0,
        items_saved=total_saved,
        error_detail=(
            None if total_saved > 0
            else "Zero items saved — slug or API may have changed"
        ),
    )
    log.info(
        "Lidl scraper: finished — %d items saved, %d skipped (non-grocery), %d errors",
        total_saved,
        skipped,
        errors,
    )


# ---------------------------------------------------------------------------
# Tesco Ireland (SSR HTML) scraper
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Dunnes Stores Ireland (SSR HTML) scraper
# ---------------------------------------------------------------------------

DUNNES_HTML_BASE_URL = (
    "https://www.dunnesstoresgrocery.com"
    "/sm/delivery/rsid/258/promotions"
)
DUNNES_HTML_SESSION_URL = (
    "https://www.dunnesstoresgrocery.com"
    "/sm/delivery/rsid/258/promotions"
)
DUNNES_HTML_PAGE_SIZE = 30
DUNNES_HTML_TOTAL_PAGES = 220  # ceil(6487/30) + safety margin

_DUNNES_PRICE_RE = re.compile(r"[\d]+[.,]\d{2}")


def _parse_dunnes_price(text: str) -> float | None:
    """Extract first decimal price from text, e.g. '€1.40' -> 1.40"""
    m = _DUNNES_PRICE_RE.search(text.replace(",", "."))
    if m:
        try:
            return float(m.group())
        except ValueError:
            pass
    return None


def _parse_dunnes_page(
    soup: BeautifulSoup,
    db,
    now: datetime,
    expires_at: datetime,
) -> int:
    """Parse one Dunnes promotions HTML page (same Mi9 SSR as SuperValu)."""
    count = 0

    cards = soup.find_all(
        lambda tag: tag.name
        and tag.get("class")
        and any("ProductCard--" in c for c in tag.get("class", []))
    )

    for card in cards:
        try:
            img = card.find("img")
            name = img.get("alt", "").strip() if img else ""
            if not name:
                aria = card.find(
                    lambda t: t.get("class")
                    and any(
                        "AriaProductTitle--" in c
                        for c in t.get("class", [])
                    )
                )
                if aria:
                    raw = aria.get_text(strip=True)
                    name = (
                        raw.split(",")[0].strip()
                        if "," in raw
                        else raw[:60]
                    )

            if not name:
                continue

            price_el = card.find(
                lambda t: t.get("class")
                and any(
                    "ProductPrice--" in c for c in t.get("class", [])
                )
            )
            price_text = price_el.get_text(strip=True) if price_el else ""
            price = _parse_dunnes_price(price_text)
            if price is None:
                continue

            promo_el = card.find(
                lambda t: t.get("class")
                and any(
                    "PromotionLabelBadge--" in c
                    for c in t.get("class", [])
                )
            )
            is_on_offer = promo_el is not None

            product_key = generate_product_key(name)

            db.table("collective_prices").upsert(
                {
                    "product_key": product_key,
                    "product_name": name,
                    "category": "Other",
                    "store_name": "Dunnes",
                    "unit_price": price,
                    "is_on_offer": is_on_offer,
                    "source": "leaflet",
                    "observed_at": now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                },
                on_conflict="product_key,store_name,source",
            ).execute()
            count += 1

        except Exception as e:
            log.warning("Dunnes HTML scraper: item error: %s", e)

    return count


async def _scrape_dunnes_attempt(
    db, use_proxy: bool = False
) -> dict:
    """Scrape Dunnes promotions page (SSR HTML).
    Uses curl-cffi to impersonate Chrome TLS fingerprint (bypasses Akamai).
    Falls back to httpx if curl-cffi is not available.
    Returns {"success": bool, "items_saved": int, "error": str|None}."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)
    errors = 0

    # Checkpoint resume
    checkpoint = _get_checkpoint(db, "Dunnes")
    start_page = checkpoint["last_page"] if checkpoint else 1
    total_saved = checkpoint["items_saved"] if checkpoint else 0
    if checkpoint:
        log.info(
            "Dunnes HTML scraper: resuming from page %d "
            "(%d items already saved)",
            start_page,
            total_saved,
        )

    # Proxy config
    proxies = None
    if use_proxy and settings.WEBSHARE_PROXY_URL:
        proxies = {
            "http": settings.WEBSHARE_PROXY_URL,
            "https": settings.WEBSHARE_PROXY_URL,
        }

    # Use curl-cffi if available (bypasses Akamai TLS fingerprinting)
    if _CURL_CFFI_AVAILABLE:
        return await _scrape_dunnes_curl(
            db, now, expires_at, start_page, total_saved, errors, proxies
        )
    else:
        # Fallback to httpx (will likely get 403 from Akamai)
        return await _scrape_dunnes_httpx(
            db, now, expires_at, start_page, total_saved, errors,
            use_proxy=use_proxy,
        )


async def _scrape_dunnes_curl(
    db, now, expires_at, start_page, total_saved, errors, proxies
) -> dict:
    """Dunnes scraper using curl-cffi (Chrome TLS impersonation)."""
    from curl_cffi.requests import AsyncSession as CurlSession

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "en-IE,en-GB;q=0.9,en;q=0.8",
        "Referer": "https://www.dunnesstoresgrocery.com/",
    }

    try:
        async with CurlSession(impersonate="chrome131") as session:
            # Session
            try:
                session_resp = await session.get(
                    DUNNES_HTML_SESSION_URL,
                    headers=headers,
                    proxies=proxies,
                    timeout=45,
                    allow_redirects=True,
                )
                if session_resp.status_code == 403:
                    return {
                        "success": False,
                        "items_saved": total_saved,
                        "error": "Session blocked (403) even with curl-cffi",
                    }
                session_resp.raise_for_status()
                log.info(
                    "Dunnes curl-cffi scraper: session OK (status %d)",
                    session_resp.status_code,
                )
            except Exception as e:
                return {
                    "success": False,
                    "items_saved": total_saved,
                    "error": str(e),
                }

            # Discover total pages from preloaded state
            total_pages = DUNNES_HTML_TOTAL_PAGES
            try:
                state_match = re.search(
                    r"window\.__PRELOADED_STATE__\s*=\s*(\{.+?\})"
                    r"\s*;?\s*</script>",
                    session_resp.text,
                    re.DOTALL,
                )
                if state_match:
                    state = _json.loads(state_match.group(1))
                    total_items = (
                        state.get("search", {})
                        .get("pagination", {})
                        .get("promotions", {})
                        .get("totalItems", 0)
                    )
                    if total_items > 0:
                        total_pages = (
                            total_items + DUNNES_HTML_PAGE_SIZE - 1
                        ) // DUNNES_HTML_PAGE_SIZE
                        log.info(
                            "Dunnes curl-cffi scraper: %d products "
                            "across %d pages",
                            total_items,
                            total_pages,
                        )
            except Exception:
                pass

            # Page 1 (already loaded)
            if start_page <= 1:
                soup_p1 = BeautifulSoup(
                    session_resp.text, "html.parser"
                )
                saved_p1 = _parse_dunnes_page(
                    soup_p1, db, now, expires_at
                )
                total_saved += saved_p1

            # Pages 2..N
            for page in range(
                start_page if start_page > 1 else 2,
                total_pages + 1,
            ):
                try:
                    resp = await session.get(
                        DUNNES_HTML_BASE_URL,
                        params={"page": page},
                        headers=headers,
                        proxies=proxies,
                        timeout=45,
                        allow_redirects=True,
                    )
                    if resp.status_code == 403:
                        errors += 1
                        log.warning(
                            "Dunnes curl-cffi: 403 on page %d", page
                        )
                        if errors >= 3:
                            break
                        await _page_delay()
                        continue
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")
                    saved = _parse_dunnes_page(
                        soup, db, now, expires_at
                    )
                    total_saved += saved
                except Exception as e:
                    errors += 1
                    log.warning(
                        "Dunnes curl-cffi: page %d error: %s", page, e
                    )

                if page % 5 == 0:
                    _save_checkpoint(
                        db, "Dunnes", page + 1, total_saved
                    )

                if page % 20 == 0:
                    log.info(
                        "Dunnes curl-cffi: %d/%d pages (%d items saved)",
                        page,
                        total_pages,
                        total_saved,
                    )

                await _page_delay()

        if total_saved > 0:
            _clear_checkpoint(db, "Dunnes")
            return {
                "success": True,
                "items_saved": total_saved,
                "error": None,
            }
        return {
            "success": False,
            "items_saved": 0,
            "error": (
                "Zero items saved — possible block or "
                "HTML structure change"
            ),
        }

    except Exception as e:
        return {
            "success": False,
            "items_saved": total_saved,
            "error": str(e),
        }


async def _scrape_dunnes_httpx(
    db, now, expires_at, start_page, total_saved, errors, use_proxy
) -> dict:
    """Fallback Dunnes scraper using httpx (less effective vs Akamai)."""
    headers = _random_headers(
        referer="https://www.dunnesstoresgrocery.com/",
        origin="https://www.dunnesstoresgrocery.com",
    )
    client_kwargs = _make_client_kwargs(use_proxy=use_proxy)
    client_kwargs["headers"] = headers

    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            try:
                session_resp = await client.get(DUNNES_HTML_SESSION_URL)
                if session_resp.status_code == 403:
                    return {
                        "success": False,
                        "items_saved": total_saved,
                        "error": "Session blocked (403)",
                    }
                session_resp.raise_for_status()
                log.info(
                    "Dunnes httpx scraper: session OK (%d cookies)",
                    len(client.cookies),
                )
            except Exception as e:
                return {
                    "success": False,
                    "items_saved": total_saved,
                    "error": str(e),
                }

            total_pages = DUNNES_HTML_TOTAL_PAGES
            soup_p1 = BeautifulSoup(
                session_resp.text, "html.parser"
            )

            if start_page <= 1:
                saved_p1 = _parse_dunnes_page(
                    soup_p1, db, now, expires_at
                )
                total_saved += saved_p1

            for page in range(
                start_page if start_page > 1 else 2,
                total_pages + 1,
            ):
                try:
                    resp = await client.get(
                        DUNNES_HTML_BASE_URL, params={"page": page}
                    )
                    if resp.status_code == 403:
                        errors += 1
                        if errors >= 3:
                            break
                        await _page_delay()
                        continue
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")
                    saved = _parse_dunnes_page(
                        soup, db, now, expires_at
                    )
                    total_saved += saved
                except Exception as e:
                    errors += 1
                    log.warning(
                        "Dunnes httpx: page %d error: %s", page, e
                    )

                if page % 5 == 0:
                    _save_checkpoint(
                        db, "Dunnes", page + 1, total_saved
                    )

                await _page_delay()

        if total_saved > 0:
            _clear_checkpoint(db, "Dunnes")
            return {
                "success": True,
                "items_saved": total_saved,
                "error": None,
            }
        return {
            "success": False,
            "items_saved": 0,
            "error": "Zero items saved",
        }

    except Exception as e:
        return {
            "success": False,
            "items_saved": total_saved,
            "error": str(e),
        }


async def scrape_dunnes_promotions() -> None:
    """Scrape Dunnes Stores promotions via HTML pages (SSR).
    Fallback chain: 0->direct, 1->Webshare proxy, 2->Apify, 3->Auto-Fix AI."""
    db = get_service_client()
    run_id = _start_run(db, "Dunnes")

    log.info("Dunnes HTML scraper: starting with fallback chain...")
    await asyncio.sleep(random.uniform(5, 10))

    # Fallback 0: direct
    result = await _scrape_dunnes_attempt(db, use_proxy=False)
    if result["success"]:
        _finish_run(
            db, run_id, status="success", fallback_level=0,
            items_saved=result["items_saved"],
        )
        log.info(
            "Dunnes HTML scraper: direct success (%d items)",
            result["items_saved"],
        )
        return
    log.warning(
        "Dunnes HTML scraper: fallback 0 failed — %s",
        result.get("error"),
    )

    # Fallback 1: Webshare proxy
    if not settings.WEBSHARE_PROXY_URL:
        log.info(
            "Dunnes HTML scraper: no proxy configured — "
            "skipping fallback 1"
        )
    else:
        log.info("Dunnes HTML scraper: trying via Webshare proxy...")
        result = await _scrape_dunnes_attempt(db, use_proxy=True)
        if result["success"]:
            _finish_run(
                db, run_id, status="success", fallback_level=1,
                items_saved=result["items_saved"],
            )
            log.info(
                "Dunnes HTML scraper: proxy success (%d items)",
                result["items_saved"],
            )
            return
        log.warning(
            "Dunnes HTML scraper: fallback 1 failed — %s",
            result.get("error"),
        )

    # Fallback 2: Apify (if configured)
    if settings.APIFY_ACTOR_DUNNES and settings.APIFY_API_TOKEN:
        log.info(
            "Dunnes HTML scraper: trying Apify actor %s...",
            settings.APIFY_ACTOR_DUNNES,
        )
        items = await _run_apify_actor(
            settings.APIFY_ACTOR_DUNNES,
            {"startUrls": [{"url": DUNNES_HTML_SESSION_URL}]},
        )
        if items:
            saved = await _save_mi9_items(db, DUNNES, items)
            _finish_run(
                db, run_id, status="success", fallback_level=2,
                items_saved=saved,
            )
            log.info(
                "Dunnes HTML scraper: Apify success (%d items)", saved
            )
            return
        log.warning(
            "Dunnes HTML scraper: fallback 2 (Apify) returned 0 items"
        )
    else:
        log.info(
            "Dunnes HTML scraper: Apify not configured — skipping"
        )

    # Fallback 3: Auto-Fix AI
    log.error(
        "Dunnes HTML scraper: all fallbacks failed — "
        "activating Auto-Fix AI"
    )
    confidence, fix = await _autofix_scraper_ai(
        "Dunnes",
        f"HTML scraper at {DUNNES_HTML_BASE_URL} failed. "
        f"Selectors: [class*='ProductCard--'], img[alt], "
        f"[class*='ProductPrice--'], [class*='PromotionLabelBadge--']. "
        f"Last error: {result.get('error', 'unknown')}",
    )
    _finish_run(
        db, run_id,
        status="failed",
        fallback_level=3,
        items_saved=0,
        error_detail=(
            f"All fallbacks failed. AutoFix: {confidence:.0%}"
        ),
        autofix_confidence=confidence,
        autofix_applied=fix is not None,
    )
    log.error("Dunnes HTML scraper: failed at all levels")


TESCO_BASE_URL = (
    "https://www.tesco.ie/groceries/en-IE/promotions/all"
)
TESCO_SESSION_URL = "https://www.tesco.ie/groceries/en-IE/"
TESCO_PAGE_SIZE = 24

_TESCO_TOTAL_RE = re.compile(
    r"of\s+([\d,]+)\s+results?", re.IGNORECASE
)
_TESCO_PRICE_RE = re.compile(r"[\d]+[.,]\d{2}")


# ---------------------------------------------------------------------------
# SuperValu Ireland (SSR HTML) scraper
# ---------------------------------------------------------------------------

SUPERVALU_BASE_URL = (
    "https://shop.supervalu.ie/sm/delivery/rsid/5550/promotions"
)
SUPERVALU_SESSION_URL = (
    "https://shop.supervalu.ie/sm/delivery/rsid/5550/promotions"
)
SUPERVALU_PAGE_SIZE = 30
SUPERVALU_TOTAL_PAGES = 1  # Pagination broken: SSR ignores ?page=N, all pages return page-1 content. Need Playwright actor for full ~3600 products.

_SUPERVALU_PRICE_RE = re.compile(r"[\d]+[.,]\d{2}")


def _parse_supervalu_price(text: str) -> float | None:
    """Extract first decimal price from text, e.g. '€1.40' -> 1.40"""
    m = _SUPERVALU_PRICE_RE.search(text.replace(",", "."))
    if m:
        try:
            return float(m.group())
        except ValueError:
            pass
    return None


def _parse_supervalu_page(
    soup: BeautifulSoup,
    db,
    now: datetime,
    expires_at: datetime,
) -> int:
    """Parse one SuperValu promotions HTML page.

    Selectors confirmed live on 25/03/2026:
    - Card container:  [class*="ProductCard--"]
    - Name:            img[alt] inside the card
    - Price:           [class*="ProductPrice--"]
    - Promo label:     [class*="PromotionLabelBadge--"]
    """
    count = 0

    cards = soup.find_all(
        lambda tag: tag.name
        and tag.get("class")
        and any("ProductCard--" in c for c in tag.get("class", []))
    )

    for card in cards:
        try:
            # Name — use img alt (cleaner than aria text)
            img = card.find("img")
            name = img.get("alt", "").strip() if img else ""
            if not name:
                # Fallback: AriaProductTitle
                aria = card.find(
                    lambda t: t.get("class")
                    and any(
                        "AriaProductTitle--" in c
                        for c in t.get("class", [])
                    )
                )
                if aria:
                    raw = aria.get_text(strip=True)
                    name = (
                        raw.split(",")[0].strip()
                        if "," in raw
                        else raw[:60]
                    )

            if not name:
                continue

            # Price
            price_el = card.find(
                lambda t: t.get("class")
                and any(
                    "ProductPrice--" in c for c in t.get("class", [])
                )
            )
            price_text = price_el.get_text(strip=True) if price_el else ""
            price = _parse_supervalu_price(price_text)
            if price is None:
                continue

            # Promotion — present only if product is on offer
            promo_el = card.find(
                lambda t: t.get("class")
                and any(
                    "PromotionLabelBadge--" in c
                    for c in t.get("class", [])
                )
            )
            is_on_offer = promo_el is not None

            product_key = generate_product_key(name)

            db.table("collective_prices").upsert(
                {
                    "product_key": product_key,
                    "product_name": name,
                    "category": "Other",
                    "store_name": "SuperValu",
                    "unit_price": price,
                    "is_on_offer": is_on_offer,
                    "source": "leaflet",
                    "observed_at": now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                },
                on_conflict="product_key,store_name,source",
            ).execute()
            count += 1

        except Exception as e:
            log.warning("SuperValu HTML scraper: item error: %s", e)

    return count


async def _scrape_supervalu_attempt(
    db, use_proxy: bool = False
) -> dict:
    """Scrape SuperValu promotions page (SSR HTML).
    Returns {"success": bool, "items_saved": int, "error": str|None}."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)
    errors = 0

    # Always start from page 1 — checkpoint removed (caused broken resume)
    start_page = 1
    total_saved = 0

    headers = _random_headers(
        referer="https://shop.supervalu.ie/",
        origin="https://shop.supervalu.ie",
    )
    client_kwargs = _make_client_kwargs(use_proxy=use_proxy)
    client_kwargs["headers"] = headers

    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            # 1. Establish session (get cookies)
            try:
                session_resp = await client.get(SUPERVALU_SESSION_URL)
                if session_resp.status_code == 403:
                    return {
                        "success": False,
                        "items_saved": 0,
                        "error": "Session blocked (403)",
                    }
                session_resp.raise_for_status()
                log.info(
                    "SuperValu HTML scraper: session OK (%d cookies)",
                    len(client.cookies),
                )
            except Exception as e:
                return {
                    "success": False,
                    "items_saved": 0,
                    "error": f"Session failed: {e}",
                }

            # 2. Discover total pages from first page
            # NOTE: Pagination is broken — SSR ignores ?page=N, all pages
            # return page-1 content. We cap at 1 page until a Playwright
            # actor is built. The state reports ~3666 items across 122
            # pages, but fetching them returns duplicate data.
            total_pages = SUPERVALU_TOTAL_PAGES  # 1 — pagination broken
            try:
                soup_p1 = BeautifulSoup(
                    session_resp.text, "html.parser"
                )
                state_match = re.search(
                    r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*;?"
                    r"\s*</script>",
                    session_resp.text,
                    re.DOTALL,
                )
                if state_match:
                    try:
                        state = _json.loads(state_match.group(1))
                        total_items = (
                            state.get("search", {})
                            .get("pagination", {})
                            .get("promotions", {})
                            .get("totalItems", 0)
                        )
                        if total_items > 0:
                            # Don't override total_pages — pagination broken
                            log.info(
                                "SuperValu HTML scraper: site reports %d products "
                                "but pagination is broken (SSR), only page 1 captured",
                                total_items,
                            )
                    except Exception:
                        pass
            except Exception:
                soup_p1 = BeautifulSoup(
                    session_resp.text, "html.parser"
                )

            # 3. Process page 1 only if not resuming past it
            if start_page <= 1:
                saved_p1 = _parse_supervalu_page(
                    soup_p1, db, now, expires_at
                )
                total_saved += saved_p1

            # 4. Iterate pages
            for page in range(max(start_page, 2), total_pages + 1):
                try:
                    resp = await client.get(
                        SUPERVALU_BASE_URL, params={"page": page}
                    )
                    if resp.status_code == 403:
                        errors += 1
                        log.warning(
                            "SuperValu HTML scraper: 403 on page %d",
                            page,
                        )
                        if errors >= 3:
                            break
                        await _page_delay()
                        continue
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")
                    saved = _parse_supervalu_page(
                        soup, db, now, expires_at
                    )
                    total_saved += saved
                except Exception as e:
                    errors += 1
                    log.warning(
                        "SuperValu HTML scraper: page %d error: %s",
                        page,
                        e,
                    )

                if page % 20 == 0:
                    log.info(
                        "SuperValu HTML scraper: %d/%d pages "
                        "(%d items saved)",
                        page,
                        total_pages,
                        total_saved,
                    )

                await _page_delay()

        if total_saved >= 100:
            # At least 100 items = meaningful data (site has ~3600).
            # 30 items means only page 1 was captured (pagination broken).
            return {
                "success": True,
                "items_saved": total_saved,
                "error": None,
            }
        return {
            "success": False,
            "items_saved": total_saved,
            "error": (
                f"Only {total_saved} items saved (threshold=100) — "
                "SSR pagination broken, falling back to Apify"
            ),
        }

    except Exception as e:
        return {"success": False, "items_saved": total_saved, "error": str(e)}


async def scrape_supervalu_promotions() -> None:
    """Scrape SuperValu Ireland promotions via HTML pages (SSR).
    Fallback chain: 0->direct, 1->Webshare proxy, 2->Apify actor, 3->Auto-Fix AI."""
    db = get_service_client()
    run_id = _start_run(db, "SuperValu")

    log.info("SuperValu HTML scraper: starting with fallback chain...")
    await asyncio.sleep(random.uniform(5, 10))

    # Fallback 0: direct
    result = await _scrape_supervalu_attempt(db, use_proxy=False)
    if result["success"]:
        _finish_run(
            db, run_id, status="success", fallback_level=0,
            items_saved=result["items_saved"],
        )
        log.info(
            "SuperValu HTML scraper: direct success (%d items)",
            result["items_saved"],
        )
        return
    log.warning(
        "SuperValu HTML scraper: fallback 0 failed — %s",
        result.get("error"),
    )

    # Fallback 1: Webshare proxy
    if not settings.WEBSHARE_PROXY_URL:
        log.info(
            "SuperValu HTML scraper: no proxy configured — "
            "skipping fallback 1"
        )
    else:
        log.info("SuperValu HTML scraper: trying via Webshare proxy...")
        result = await _scrape_supervalu_attempt(db, use_proxy=True)
        if result["success"]:
            _finish_run(
                db, run_id, status="success", fallback_level=1,
                items_saved=result["items_saved"],
            )
            log.info(
                "SuperValu HTML scraper: proxy success (%d items)",
                result["items_saved"],
            )
            return
        log.warning(
            "SuperValu HTML scraper: fallback 1 failed — %s",
            result.get("error"),
        )

    # Fallback 2: Apify Playwright actor
    if settings.APIFY_API_TOKEN and settings.APIFY_ACTOR_SUPERVALU:
        log.info(
            "SuperValu scraper: trying Apify actor %s...",
            settings.APIFY_ACTOR_SUPERVALU,
        )
        items = await _run_apify_actor(
            settings.APIFY_ACTOR_SUPERVALU,
            {"maxPages": 130},
        )
        if items:
            saved = _save_supervalu_apify_items(db, items)
            _finish_run(
                db, run_id, status="success", fallback_level=2,
                items_saved=saved,
            )
            log.info(
                "SuperValu scraper: success via Apify (%d items)", saved
            )
            return
        log.warning(
            "SuperValu scraper: fallback 2 (Apify) returned 0 items"
        )
    else:
        log.info(
            "SuperValu scraper: Apify not configured — skipping"
        )

    # Fallback 3: Auto-Fix AI
    log.error(
        "SuperValu HTML scraper: all fallbacks failed — "
        "activating Auto-Fix AI"
    )
    confidence, fix = await _autofix_scraper_ai(
        "SuperValu",
        f"HTML scraper at {SUPERVALU_BASE_URL} failed. "
        f"Selectors: [class*='ProductCard--'], img[alt], "
        f"[class*='ProductPrice--'], [class*='PromotionLabelBadge--']. "
        f"Last error: {result.get('error', 'unknown')}",
    )
    _finish_run(
        db, run_id,
        status="failed",
        fallback_level=3,
        items_saved=0,
        error_detail=(
            f"All fallbacks failed. AutoFix: {confidence:.0%}"
        ),
        autofix_confidence=confidence,
        autofix_applied=fix is not None,
    )
    log.error("SuperValu HTML scraper: failed at all levels")


def _save_supervalu_apify_items(db, items: list) -> int:
    """Save items from Apify SuperValu Playwright actor.

    The custom Playwright actor returns:
      {"name": "...", "price": "€2.50", "promotion": "3 for €10", "page": 1}
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)
    count = 0
    errors = 0
    for item in items:
        try:
            name = item.get("name")
            # Clean name: strip UI artifacts from Playwright extraction
            if name:
                name = (
                    name.replace("Open Product Description", "")
                    .strip()
                )
            price_raw = item.get("price") or ""
            # Handle €3.00, €3,00, and multi-price formats like "€2.50 was €3.00"
            price_str = str(price_raw).replace(",", ".")
            price_match = re.search(r"[\d]+\.[\d]{2}", price_str)
            price = float(price_match.group()) if price_match else None
            if not name or price is None:
                continue

            promo = item.get("promotion")
            is_on_offer = bool(promo)

            product_key = generate_product_key(name)

            db.table("collective_prices").upsert(
                {
                    "product_key": product_key,
                    "product_name": name,
                    "category": "Other",
                    "store_name": "SuperValu",
                    "unit_price": float(price),
                    "is_on_offer": is_on_offer,
                    "source": "leaflet",
                    "observed_at": now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                },
                on_conflict="product_key,store_name,source",
            ).execute()
            count += 1
        except Exception as e:
            errors += 1
            log.warning("_save_supervalu_apify_items: item error: %s", e)
            if errors <= 3:
                try:
                    import sentry_sdk
                    sentry_sdk.capture_exception(e)
                except Exception:
                    pass

    log.info(
        "_save_supervalu_apify_items: saved %d/%d items (%d errors)",
        count, len(items), errors,
    )
    return count


def _parse_tesco_price(text: str) -> float | None:
    """Extract the first decimal price from a text string."""
    m = _TESCO_PRICE_RE.search(text.replace(",", "."))
    if m:
        try:
            return float(m.group())
        except ValueError:
            pass
    return None


async def _scrape_tesco_attempt(
    db, use_proxy: bool = False
) -> dict:
    """One Tesco scrape attempt. Returns success/items_saved/error dict."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)
    mode = "proxy" if use_proxy else "direct"
    label = f"Tesco({mode})"

    # Always start from page 1 — checkpoint removed (caused broken resume)
    start_page = 1
    total_saved = 0

    tesco_headers = _random_headers(
        referer="https://www.tesco.ie/",
        origin="https://www.tesco.ie",
    )
    tesco_headers["Accept-Encoding"] = "gzip, deflate, br"
    tesco_headers["Cache-Control"] = "no-cache"

    client_kwargs = _make_client_kwargs(use_proxy=use_proxy)
    client_kwargs["headers"] = tesco_headers

    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            try:
                session_resp = await client.get(TESCO_SESSION_URL)
                session_resp.raise_for_status()
                log.info(
                    "%s: session OK (%d cookies)",
                    label,
                    len(client.cookies),
                )
            except Exception as e:
                return {
                    "success": False, "items_saved": 0, "error": str(e)
                }

            total_pages = 1
            page = start_page

            while page <= total_pages:
                params = {
                    "sortBy": "relevance",
                    "page": page,
                    "count": TESCO_PAGE_SIZE,
                }
                try:
                    resp = await client.get(
                        TESCO_BASE_URL, params=params
                    )
                    resp.raise_for_status()
                    html = resp.text
                except Exception as e:
                    log.warning(
                        "%s: page %d failed (%s)", label, page, e
                    )
                    await _page_delay()
                    page += 1
                    continue

                soup = BeautifulSoup(html, "html.parser")

                if page == 1:
                    results_text = soup.get_text()
                    m = _TESCO_TOTAL_RE.search(results_text)
                    if m:
                        total_items_count = int(
                            m.group(1).replace(",", "")
                        )
                        total_pages = (
                            total_items_count + TESCO_PAGE_SIZE - 1
                        ) // TESCO_PAGE_SIZE
                        log.info(
                            "%s: %d products across %d pages",
                            label,
                            total_items_count,
                            total_pages,
                        )

                product_links = soup.select(
                    "a[href*='/groceries/en-IE/products/']"
                )
                for link in product_links:
                    try:
                        name = link.get_text(strip=True)
                        if not name:
                            continue

                        container = link
                        for _ in range(8):
                            if container.parent is None:
                                break
                            container = container.parent
                            price_el = container.select_one(
                                "[class*='product-tile-price__text'],"
                                "[class*='price-text'],"
                                "[class*='value']"
                            )
                            if price_el:
                                break

                        price = None
                        price_el = container.select_one(
                            "[class*='product-tile-price__text'],"
                            "[class*='price-text'],"
                            "[class*='price-per-sellable-unit']"
                        )
                        if price_el:
                            price = _parse_tesco_price(
                                price_el.get_text()
                            )

                        if price is None:
                            for el in container.find_all(
                                string=re.compile(r"€")
                            ):
                                price = _parse_tesco_price(str(el))
                                if price is not None:
                                    break

                        if price is None:
                            continue

                        promo_el = container.select_one(
                            "[class*='value-bar__content-text'],"
                            "[class*='promo'],"
                            "[class*='offer']"
                        )
                        is_on_offer = promo_el is not None
                        product_key = generate_product_key(name)

                        db.table("collective_prices").upsert(
                            {
                                "product_key": product_key,
                                "product_name": name,
                                "category": "Other",
                                "store_name": "Tesco",
                                "unit_price": price,
                                "is_on_offer": is_on_offer,
                                "source": "leaflet",
                                "observed_at": now.isoformat(),
                                "expires_at": expires_at.isoformat(),
                            },
                            on_conflict="product_key,store_name,source",
                        ).execute()
                        total_saved += 1

                    except Exception as e:
                        log.warning(
                            "%s: item error on page %d: %s",
                            label, page, e,
                        )

                if page % 10 == 0:
                    log.info(
                        "%s: %d/%d pages (%d items)",
                        label, page, total_pages, total_saved,
                    )

                await _page_delay()
                page += 1

        if total_saved >= 50:
            # Less than 50 items = likely blocked (session page only)
            return {
                "success": True, "items_saved": total_saved, "error": None
            }
        return {
            "success": False,
            "items_saved": total_saved,
            "error": (
                f"Only {total_saved} items saved (threshold=50) — "
                "likely blocked, falling back to Apify"
            ),
        }

    except Exception as e:
        return {"success": False, "items_saved": total_saved, "error": str(e)}


def _save_tesco_apify_items(db, items: list) -> int:
    """Save items from Apify actor pasquetto/my-actor.

    The custom Playwright actor returns:
      {"name": "...", "price": "€3.00", "promotion": "Clubcard Price...", "page": 1}
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)
    count = 0
    errors = 0
    for item in items:
        try:
            name = item.get("name")
            price_raw = item.get("price") or item.get("priceText") or ""
            # Handle both €3.00 and €3,00 formats
            price_str = str(price_raw).replace(",", ".")
            price_match = re.search(r"[\d]+\.[\d]{2}", price_str)
            price = float(price_match.group()) if price_match else None
            if not name or price is None:
                continue

            promo = item.get("promotion")
            # promo is a plain string from the custom actor (e.g. "Clubcard Price...")
            # not a dict — just use it directly for is_on_offer flag
            is_on_offer = bool(promo)

            product_key = generate_product_key(name)
            category = (
                item.get("category")
                or item.get("main_category")
                or item.get("product_category")
                or "Other"
            )

            db.table("collective_prices").upsert(
                {
                    "product_key": product_key,
                    "product_name": name,
                    "category": category,
                    "store_name": "Tesco",
                    "unit_price": float(price),
                    "is_on_offer": is_on_offer,
                    "source": "leaflet",
                    "observed_at": now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                },
                on_conflict="product_key,store_name,source",
            ).execute()
            count += 1
        except Exception as e:
            errors += 1
            log.warning("_save_tesco_apify_items: item error: %s", e)
            if errors <= 3:
                try:
                    import sentry_sdk
                    sentry_sdk.capture_exception(e)
                except Exception:
                    pass

    log.info(
        "_save_tesco_apify_items: saved %d/%d items (%d errors)",
        count, len(items), errors,
    )
    return count


async def scrape_tesco_promotions() -> None:
    """Scrape Tesco Ireland with full fallback chain."""
    db = get_service_client()
    run_id = _start_run(db, "Tesco")

    log.info("Tesco scraper: starting with fallback chain...")
    await asyncio.sleep(random.uniform(8, 15))

    # Fallback 0: direct
    result = await _scrape_tesco_attempt(db, use_proxy=False)
    if result["success"]:
        _finish_run(
            db, run_id, status="success", fallback_level=0,
            items_saved=result["items_saved"],
        )
        log.info(
            "Tesco scraper: success direct (%d items)",
            result["items_saved"],
        )
        return
    log.warning(
        "Tesco scraper: fallback 0 failed — %s", result.get("error")
    )

    # Fallback 1: Webshare proxy
    if not settings.WEBSHARE_PROXY_URL:
        log.info("Tesco scraper: WEBSHARE_PROXY_URL not set — skipping")
    else:
        log.info("Tesco scraper: trying via Webshare proxy...")
        result = await _scrape_tesco_attempt(db, use_proxy=True)
        if result["success"]:
            _finish_run(
                db, run_id, status="success", fallback_level=1,
                items_saved=result["items_saved"],
            )
            log.info(
                "Tesco scraper: success via proxy (%d items)",
                result["items_saved"],
            )
            return
        log.warning(
            "Tesco scraper: fallback 1 failed — %s", result.get("error")
        )

    # Fallback 2: Apify
    if settings.APIFY_API_TOKEN and settings.APIFY_ACTOR_TESCO:
        log.info(
            "Tesco scraper: trying Apify actor %s...",
            settings.APIFY_ACTOR_TESCO,
        )
        items = await _run_apify_actor(
            settings.APIFY_ACTOR_TESCO,
            {
                "maxPages": 24,
            },
        )
        if items:
            saved = _save_tesco_apify_items(db, items)
            _finish_run(
                db, run_id, status="success", fallback_level=2,
                items_saved=saved,
            )
            log.info(
                "Tesco scraper: success via Apify (%d items)", saved
            )
            return
        log.warning("Tesco scraper: fallback 2 (Apify) returned 0 items")
    else:
        log.info("Tesco scraper: Apify not configured — skipping")

    # Fallback 3: Auto-Fix AI
    log.warning(
        "Tesco scraper: all fallbacks failed — activating Auto-Fix AI"
    )
    confidence, fix = await _autofix_scraper_ai(
        "Tesco",
        f"TESCO_BASE_URL ({TESCO_BASE_URL}) returns 403. "
        f"Session at {TESCO_SESSION_URL} works (200). "
        f"Last error: {result.get('error', 'unknown')}",
    )
    _finish_run(
        db, run_id,
        status="failed",
        fallback_level=3,
        items_saved=0,
        error_detail=(
            f"All fallbacks failed. AutoFix: {confidence:.0%}"
        ),
        autofix_confidence=confidence,
        autofix_applied=fix is not None,
    )
    log.warning("Tesco scraper: failed at all levels")


# ---------------------------------------------------------------------------
# Leaflet jobs
# ---------------------------------------------------------------------------


async def scrape_aldi_leaflet() -> None:
    """Scrape Aldi Ireland leaflet using Apify Playwright actor + OCR.

    Flow:
    1. Apify actor navigates leaflet.aldi.ie pages 1-7 and captures images
    2. Backend fetches page images from Apify dataset (base64)
    3. Each image is OCR'd with Gemini, then products extracted with GPT
    4. Products saved to collective_prices
    """
    from app.services.ocr_service import extract_text_from_pdf_page
    from app.services.extraction_service import extract_leaflet_products

    db = get_service_client()
    run_id = _start_run(db, "Aldi")
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=7)
    total_saved = 0
    errors = 0

    actor_id = settings.APIFY_ACTOR_ALDI
    if not actor_id or not settings.APIFY_API_TOKEN:
        log.info("Aldi scraper: Apify not configured — skipping")
        _finish_run(
            db, run_id, status="failed", fallback_level=0,
            items_saved=0,
            error_detail="APIFY_ACTOR_ALDI not configured",
        )
        return

    log.info("Aldi scraper: starting Apify actor %s...", actor_id)

    # Run actor (smart reuse will use recent dataset if available)
    items = await _run_apify_actor(
        actor_id,
        {"maxPages": 7},
        timeout_secs=600,
        poll_interval=20,
    )

    if not items:
        log.warning("Aldi scraper: Apify returned 0 items")
        _finish_run(
            db, run_id, status="failed", fallback_level=0,
            items_saved=0,
            error_detail="Apify actor returned 0 pages",
        )
        return

    log.info("Aldi scraper: processing %d page images...", len(items))

    import base64

    for item in items:
        page_num = item.get("page", 0)
        image_b64 = item.get("image_base64", "")

        if not image_b64:
            log.warning("Aldi scraper: page %d has no image", page_num)
            continue

        try:
            # Decode base64 → bytes
            # Handle data:image/jpeg;base64,... prefix
            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]
            img_bytes = base64.b64decode(image_b64)

            # OCR the page image
            raw_text = await extract_text_from_pdf_page(img_bytes)
            if not raw_text or len(raw_text) < 20:
                log.info(
                    "Aldi scraper: page %d — OCR returned too little text (%d chars)",
                    page_num, len(raw_text or ""),
                )
                continue

            # Extract products with GPT
            products = await extract_leaflet_products(raw_text, "Aldi")
            log.info(
                "Aldi scraper: page %d — %d products extracted",
                page_num, len(products),
            )

            for product in products:
                try:
                    name = product.get("product_name", "")
                    price = product.get("unit_price")
                    if not name or price is None or float(price) <= 0:
                        continue

                    from app.utils.price_utils import get_ttl_days
                    category = product.get("category", "Other")
                    ttl_days = get_ttl_days(category)

                    product_key = generate_product_key(
                        name, product.get("unit"),
                    )
                    db.table("collective_prices").upsert(
                        {
                            "product_key": product_key,
                            "product_name": name,
                            "category": category,
                            "store_name": "Aldi",
                            "unit_price": float(price),
                            "unit": product.get("unit"),
                            "is_on_offer": product.get("is_on_offer", True),
                            "source": "leaflet",
                            "observed_at": now.isoformat(),
                            "expires_at": (
                                now + timedelta(days=max(ttl_days, 7))
                            ).isoformat(),
                        },
                        on_conflict="product_key,store_name,source",
                    ).execute()
                    total_saved += 1
                except Exception as e:
                    errors += 1
                    log.warning("Aldi scraper: item save error: %s", e)

        except Exception as e:
            errors += 1
            log.warning("Aldi scraper: page %d processing error: %s", page_num, e)

    _finish_run(
        db, run_id,
        status="success" if total_saved > 0 else "failed",
        fallback_level=0,
        items_saved=total_saved,
        error_detail=(
            None if total_saved > 0
            else f"Zero items after OCR ({len(items)} pages processed)"
        ),
    )
    log.info(
        "Aldi scraper: finished — %d items saved, %d errors",
        total_saved, errors,
    )


async def run_leaflet_job():
    """Run Aldi leaflet scraper via Apify actor + OCR."""
    log.info("Starting Aldi leaflet scraper (Apify + OCR)...")
    try:
        await scrape_aldi_leaflet()
    except Exception as e:
        log.error(f"Aldi scraper failed: {e}")


async def run_dunnes_scraper():
    """Dunnes scraper disabled — Akamai blocks all automated access.
    Dunnes prices will be populated from user receipt scans.
    Re-enable when a suitable proxy/actor solution is available."""
    log.info(
        "Dunnes scraper disabled — skipping (uses receipt data instead)"
    )


async def run_supervalu_scraper():
    """Run SuperValu scraper with full fallback chain.
    HTML scraper captures page 1 (~30 products), then falls back to
    Apify Playwright actor for full pagination (~3600+ products)."""
    log.info("Starting SuperValu HTML promotions scraper...")
    try:
        await scrape_supervalu_promotions()
    except Exception as e:
        log.error(f"SuperValu scraper failed: {e}")


async def run_lidl_scraper():
    """Run Lidl leaflet scraper using Schwarz API structured data."""
    log.info("Starting Lidl leaflet scraper (structured API)...")
    try:
        await scrape_lidl_leaflet()
    except Exception as e:
        log.error(f"Lidl scraper failed: {e}")


async def run_tesco_scraper():
    """Run Tesco promotions scraper standalone."""
    log.info("Starting Tesco promotions scraper...")
    try:
        await scrape_tesco_promotions()
    except Exception as e:
        log.error(f"Tesco scraper failed: {e}")


def setup_leaflet_scheduler(scheduler: AsyncIOScheduler):
    """Schedule leaflet and store scraper jobs."""
    # PDF leaflets (Aldi) — weekly on configured day
    scheduler.add_job(
        run_leaflet_job,
        "cron",
        day_of_week=f"{settings.LEAFLET_CRON_DAY}",
        hour=settings.LEAFLET_CRON_HOUR,
        minute=0,
        id="leaflet_worker",
        replace_existing=True,
    )
    log.info(
        "Leaflet worker scheduled: day=%s, hour=%s",
        settings.LEAFLET_CRON_DAY,
        settings.LEAFLET_CRON_HOUR,
    )

    # Dunnes — disabled (Akamai blocks automated access)
    # Dunnes prices populated from user receipt scans instead.
    log.info("Dunnes scraper disabled — prices from receipt scans only")

    # SuperValu — odd days at 06:00 (day 1,3,5,...,31)
    scheduler.add_job(
        run_supervalu_scraper,
        "cron",
        day="1-31/2",
        hour=6,
        minute=0,
        id="supervalu_scraper",
        replace_existing=True,
    )
    log.info("SuperValu scraper scheduled: odd days at 06:00")

    # Tesco — even days at 07:00 (day 2,4,6,...,30)
    scheduler.add_job(
        run_tesco_scraper,
        "cron",
        day="2-30/2",
        hour=7,
        minute=0,
        id="tesco_scraper",
        replace_existing=True,
    )
    log.info("Tesco scraper scheduled: even days at 07:00")

    # Lidl — every Thursday at 07:00
    scheduler.add_job(
        run_lidl_scraper,
        "cron",
        day_of_week="thu",
        hour=7,
        minute=0,
        id="lidl_scraper",
        replace_existing=True,
    )
    log.info("Lidl scraper scheduled: Thu at 07:00")
