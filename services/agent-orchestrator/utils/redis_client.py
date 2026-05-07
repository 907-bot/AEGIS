"""Async Redis client — redis-py async."""
from __future__ import annotations
import json
import os
import redis.asyncio as aioredis

_redis: aioredis.Redis | None = None

async def init_redis() -> None:
    global _redis
    url = os.getenv("REDIS_URL", "redis://localhost:6379")
    _redis = aioredis.from_url(url, encoding="utf-8", decode_responses=True)
    await _redis.ping()
    print("✅ Redis (asyncio) connected")

def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialized")
    return _redis

async def publish_event(investigation_id: str, event: dict) -> None:
    redis = get_redis()
    channel = f"investigation:{investigation_id}:events"
    await redis.publish(channel, json.dumps(event))
