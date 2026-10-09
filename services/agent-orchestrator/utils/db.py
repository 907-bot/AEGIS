"""Async PostgreSQL pool — asyncpg."""
from __future__ import annotations
import os
import ssl
import asyncpg

_pool: asyncpg.Pool | None = None

def _get_ssl_context(dsn: str):
    db_ssl = os.getenv("DB_SSL", "").lower()
    if db_ssl in ("false", "0", "no", "disable"):
        return False
    # If production, neon, or explicitly requested
    if "neon.tech" in dsn or os.getenv("PYTHON_ENV") == "production" or db_ssl in ("true", "1", "require"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return False

async def init_db() -> None:
    global _pool
    dsn = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/aegis")
    ssl_context = _get_ssl_context(dsn)

    try:
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=5,
            command_timeout=60,
            ssl=ssl_context
        )
        print("✅ asyncpg pool ready")
    except Exception as e:
        if ssl_context is not False:
            print(f"⚠️ asyncpg SSL connection failed ({e}), retrying without SSL...")
            _pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=1,
                max_size=5,
                command_timeout=60,
                ssl=False
            )
            print("✅ asyncpg pool ready (without SSL)")
        else:
            raise

async def get_db_pool() -> asyncpg.Pool:
    if _pool is None:
        await init_db()
    return _pool  # type: ignore
