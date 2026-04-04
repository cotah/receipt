"""Simple in-memory rate limiter for FastAPI.

Uses a sliding window counter per IP address. Lightweight, no external deps.
For multi-instance deployment, switch to Redis-backed (Upstash).
"""

import time
import logging
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger(__name__)

# Sliding window: {ip: [(timestamp, count)]}
_buckets: dict[str, list[float]] = defaultdict(list)

# Config
RATE_LIMIT = 120          # requests per window
RATE_WINDOW = 60          # seconds
SCAN_RATE_LIMIT = 10      # receipt uploads per window
SCAN_RATE_WINDOW = 300    # 5 minutes

# Paths with stricter limits
SCAN_PATHS = {"/api/v1/receipts/upload", "/api/v1/receipts/upload-multi"}
AUTH_PATHS = {"/api/v1/payments/create-checkout", "/api/v1/chat/message"}
AUTH_RATE_LIMIT = 20       # auth/payment attempts per window
AUTH_RATE_WINDOW = 300     # 5 minutes
EXEMPT_PATHS = {"/health", "/docs", "/openapi.json"}


def _get_client_ip(request: Request) -> str:
    """Get client IP, respecting X-Forwarded-For from Railway proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate(key: str, limit: int, window: int) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    now = time.time()
    cutoff = now - window

    # Clean old entries
    _buckets[key] = [t for t in _buckets[key] if t > cutoff]

    if len(_buckets[key]) >= limit:
        return False

    _buckets[key].append(now)
    return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip exempt paths
        if path in EXEMPT_PATHS:
            return await call_next(request)

        ip = _get_client_ip(request)

        # Stricter limit for scan endpoints
        if path in SCAN_PATHS:
            scan_key = f"scan:{ip}"
            if not _check_rate(scan_key, SCAN_RATE_LIMIT, SCAN_RATE_WINDOW):
                log.warning(f"Scan rate limit hit: {ip}")
                raise HTTPException(
                    status_code=429,
                    detail="Too many receipt uploads. Please wait a few minutes.",
                )

        # Stricter limit for payment/chat endpoints
        if path in AUTH_PATHS:
            auth_key = f"auth:{ip}"
            if not _check_rate(auth_key, AUTH_RATE_LIMIT, AUTH_RATE_WINDOW):
                log.warning(f"Auth/payment rate limit hit: {ip} on {path}")
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please wait a few minutes.",
                )

        # General rate limit
        general_key = f"general:{ip}"
        if not _check_rate(general_key, RATE_LIMIT, RATE_WINDOW):
            log.warning(f"Rate limit hit: {ip} on {path}")
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please slow down.",
            )

        return await call_next(request)
