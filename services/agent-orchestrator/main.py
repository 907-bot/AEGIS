"""
AEGIS Agent Orchestrator — FastAPI Main
Python 3.11 | All 7 agents + Debate Chamber + Meta-Learning
Uses ARQ for background job processing (replaces Temporal/BackgroundTasks)
"""
from __future__ import annotations

import os
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, Any

import structlog
import uvicorn
from dotenv import load_dotenv
from arq import create_pool
from arq.connections import RedisSettings

# Load environment variables
python_env = os.getenv("PYTHON_ENV", "development")
if python_env != "production":
    load_dotenv(".env")
    load_dotenv("../../.env")

# Debug Environment (Safe)
redis_url = os.getenv("REDIS_URL", "not set")
masked_redis = redis_url.split("@")[-1] if "@" in redis_url else redis_url
print(f"🔍 DEBUG: PYTHON_ENV='{python_env}'")
print(f"🔍 DEBUG: REDIS_URL='{masked_redis}'")


from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from utils.redis_client import init_redis, get_redis

# ─── Logging ──────────────────────────────────────────────────────────────────
log = structlog.get_logger()

# ─── Metrics ──────────────────────────────────────────────────────────────────
INVESTIGATIONS_TOTAL   = Counter("aegis_investigations_total", "Total investigations", ["type", "status"])

# ─── App State ────────────────────────────────────────────────────────────────
arq_pool:          Optional[Any]              = None  # ARQ Redis pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    global arq_pool

    log.info("🚀 AEGIS Agent Orchestrator starting up...")

    # Initialize Redis (for status checks and pub/sub)
    try:
        await init_redis()
        log.info("✅ Redis connected")
    except Exception as e:
        log.error("❌ Redis connection failed", error=str(e))

    # Initialize ARQ Redis pool (for job queuing)
    try:
        arq_pool = await create_pool(RedisSettings.from_dsn(os.environ["REDIS_URL"]))
        log.info("✅ ARQ Redis pool connected")
    except Exception as e:
        log.error("❌ ARQ Redis pool connection failed", error=str(e))

    log.info("✅ All services initialisation attempt complete")
    yield
    # Shutdown
    if arq_pool:
        await arq_pool.close()
    log.info("👋 AEGIS Agent Orchestrator shut down")


app = FastAPI(
    title="AEGIS Agent Orchestrator",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://907-bot.github.io",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8000",
        "http://localhost:8001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Request / Response Models ────────────────────────────────────────────────
class InvestigationRequest(BaseModel):
    investigation_id: str
    url:              str
    type:             str = "competitive"
    user_id:          str = "demo-user"
    strategy_config:  dict = {}

class InvestigationStatus(BaseModel):
    investigation_id: str
    status:           str
    progress:         int
    current_agent:    Optional[str] = None
    confidence:       Optional[float] = None

# ─── Routes ───────────────────────────────────────────────────────────────────
@app.get("/")
async def root_health():
    """Root health endpoint for Render and load balancers."""
    return {"status": "ok", "service": "aegis-orchestrator"}

@app.get("/health")
async def health():
    """Health check - verifies Redis connectivity for ARQ."""
    status = "ok"
    details = {}

    try:
        redis = get_redis()
        await redis.ping()
        details["redis"] = "ok"
    except Exception as e:
        status = "degraded"
        details["redis"] = str(e)

    # Check ARQ pool
    try:
        if arq_pool:
            details["arq"] = "ok"
        else:
            status = "degraded"
            details["arq"] = "not initialized"
    except Exception as e:
        status = "degraded"
        details["arq"] = str(e)

    return {
        "status": status,
        "service": "agent-orchestrator",
        "timestamp": datetime.utcnow(),
        "details": details
    }

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/investigate")
async def start_investigation(req: InvestigationRequest):
    """
    Kick off the full AEGIS investigation pipeline via ARQ:
      1. Parallel agent reconnaissance (7 agents)
      2. Knowledge graph population
      3. Debate chamber (Bull / Bear / Skeptic / Synthesizer)
      4. Report generation
      5. Meta-learning update
    """
    log.info("investigation_started", id=req.investigation_id, url=req.url)
    INVESTIGATIONS_TOTAL.labels(type=req.type, status="started").inc()

    # Enqueue job to ARQ worker instead of using BackgroundTasks
    await arq_pool.enqueue_job(
        "run_investigation",
        req.investigation_id,
        req.url,
        req.type,
        req.user_id,
        req.strategy_config,
    )
    return {"workflow_id": req.investigation_id, "status": "queued"}

@app.get("/investigations/{investigation_id}/status")
async def get_status(investigation_id: str) -> InvestigationStatus:
    redis = get_redis()
    raw = await redis.get(f"inv:status:{investigation_id}")
    if not raw:
        raise HTTPException(status_code=404, detail="Investigation not found")
    data = json.loads(raw)
    return InvestigationStatus(**data)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True, log_level="info")
