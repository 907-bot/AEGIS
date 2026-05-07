"""Async PostgreSQL pool — asyncpg."""
from __future__ import annotations
import os
import asyncpg

_pool: asyncpg.Pool | None = None

async def init_db() -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/aegis"),
        min_size=2,
        max_size=10,
        command_timeout=60,
    )
    print("✅ asyncpg pool ready")

async def get_db_pool() -> asyncpg.Pool:
    if _pool is None:
        await init_db()
    return _pool  # type: ignore
