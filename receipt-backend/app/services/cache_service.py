import json
import logging
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)

_redis = None


def _get_redis():
    """Lazy-init the Upstash Redis client. Returns None if not configured."""
    global _redis  # noqa: PLW0603
    if _redis is not None:
        return _redis
    if not settings.UPSTASH_REDIS_URL or not settings.UPSTASH_REDIS_TOKEN:
        return None
    try:
        from upstash_redis import Redis

        _redis = Redis(
            url=settings.UPSTASH_REDIS_URL,
            token=settings.UPSTASH_REDIS_TOKEN,
        )
        log.info("Upstash Redis connected")
        return _redis
    except Exception as e:
        log.warning("Upstash Redis init failed: %s", e)
        return None


def get_cache(key: str) -> Any | None:
    """Get a value from cache. Returns None on miss or if Redis is unavailable."""
    redis = _get_redis()
    if redis is None:
        return None
    try:
        raw = redis.get(key)
        if raw is None:
            return None
        if isinstance(raw, str):
            return json.loads(raw)
        return raw
    except Exception as e:
        log.warning("Cache GET error for %s: %s", key, e)
        return None


def set_cache(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    """Set a value in cache with TTL. Returns False if Redis is unavailable."""
    redis = _get_redis()
    if redis is None:
        return False
    try:
        serialized = json.dumps(value, default=str)
        redis.set(key, serialized, ex=ttl_seconds)
        return True
    except Exception as e:
        log.warning("Cache SET error for %s: %s", key, e)
        return False
