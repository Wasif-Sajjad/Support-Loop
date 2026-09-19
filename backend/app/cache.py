"""Epic F2 — semantic cache. Starter stub: exact-text cache only. Upgrade to embedding
similarity (encode the query, store vectors, compare cosine similarity against a
threshold) as its own story — see docs/architecture.md 3.2.
"""
import hashlib
import json
import redis.asyncio as redis

from app.config import settings

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _key(ticket_text: str) -> str:
    return "cache:" + hashlib.sha256(ticket_text.strip().lower().encode()).hexdigest()


async def get_cached_answer(ticket_text: str) -> dict | None:
    r = get_redis()
    raw = await r.get(_key(ticket_text))
    return json.loads(raw) if raw else None


async def set_cached_answer(ticket_text: str, payload: dict, ttl_seconds: int = 86400) -> None:
    r = get_redis()
    await r.set(_key(ticket_text), json.dumps(payload), ex=ttl_seconds)
