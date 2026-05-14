"""
ARQ Worker wrapped as Web Service for Render Free Tier.
Runs ARQ worker + minimal health endpoint to prevent sleeping.
"""
import asyncio
import os
import signal
import sys
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as aioredis
import uvicorn
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI

from worker import WorkerSettings, run_investigation, startup, shutdown

# Global state
arq_worker_task = None
ctx = {}


async def run_arq_worker():
    """Run ARQ worker in background."""
    from arq.worker import Worker
    from arq.connections import RedisSettings
    
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    
    # Initialize the worker with settings from worker.py
    # This will automatically call startup(ctx) and shutdown(ctx)
    worker = Worker(
        functions=WorkerSettings.functions,
        on_startup=WorkerSettings.on_startup,
        on_shutdown=WorkerSettings.on_shutdown,
        redis_settings=RedisSettings.from_dsn(redis_url),
        max_jobs=WorkerSettings.max_jobs,
        job_timeout=WorkerSettings.job_timeout,
        keep_result=WorkerSettings.keep_result,
    )
    
    print("✅ ARQ Worker starting — listening for jobs...")
    try:
        await worker.main()
    except Exception as e:
        print(f"❌ ARQ Worker crashed: {e}")
    finally:
        print("👋 ARQ Worker shut down")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start ARQ worker in background on startup."""
    global arq_worker_task
    
    # Start worker as background task
    arq_worker_task = asyncio.create_task(run_arq_worker())
    
    yield
    
    # Shutdown
    if arq_worker_task:
        arq_worker_task.cancel()
        try:
            await arq_worker_task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    """Root health check — keeps Render free service alive."""
    return {
        "status": "ok",
        "service": "aegis-arq-worker",
        "type": "background-worker-on-web-tier"
    }


@app.get("/health")
async def health():
    """Health check for Render."""
    try:
        # Quick Redis connectivity check
        redis = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
        await redis.ping()
        await redis.close()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8002))
    uvicorn.run("worker_web:app", host="0.0.0.0", port=port, log_level="info")
