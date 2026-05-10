"""
AEGIS Agent Orchestrator — FastAPI Main
Python 3.11 | All 7 agents + Debate Chamber + Meta-Learning
"""
from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import structlog
import uvicorn
from dotenv import load_dotenv

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


from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from agents.sentry import SentryAgent
from agents.financial import FinancialArchaeologist
from agents.talent import TalentFlowAgent
from agents.tech_stack import TechStackAgent
from agents.sentiment import SentimentScout
from agents.regulatory import RegulatoryRadar
from agents.competitive import CompetitiveCartographer
from debate.crew import AegisDebateCrew
from memory.experience_bank import ExperienceBank
from memory.knowledge_graph import KnowledgeGraphService
from workflows.investigation import InvestigationWorkflow
from utils.db import init_db, get_db_pool
from utils.redis_client import init_redis, get_redis, publish_event
from utils.llm_router import LLMRouter

# ─── Logging ──────────────────────────────────────────────────────────────────
log = structlog.get_logger()

# ─── Metrics ──────────────────────────────────────────────────────────────────
INVESTIGATIONS_TOTAL   = Counter("aegis_investigations_total", "Total investigations", ["type", "status"])
INVESTIGATION_DURATION = Histogram("aegis_investigation_duration_seconds", "Investigation duration")
AGENT_ERRORS           = Counter("aegis_agent_errors_total", "Agent errors", ["agent"])

# ─── App State ────────────────────────────────────────────────────────────────
llm_router:        Optional[LLMRouter]        = None
experience_bank:   Optional[ExperienceBank]   = None
knowledge_graph:   Optional[KnowledgeGraphService] = None
debate_crew:       Optional[AegisDebateCrew]  = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm_router, experience_bank, knowledge_graph, debate_crew

    log.info("🚀 AEGIS Agent Orchestrator starting up...")
    
    try:
        await init_db()
        log.info("✅ Database connected")
    except Exception as e:
        log.error("❌ Database connection failed", error=str(e))

    try:
        await init_redis()
        log.info("✅ Redis connected")
    except Exception as e:
        log.error("❌ Redis connection failed", error=str(e))

    llm_router      = LLMRouter()
    experience_bank = ExperienceBank()
    knowledge_graph = KnowledgeGraphService()
    debate_crew     = AegisDebateCrew(llm_router)

    try:
        await knowledge_graph.connect()
        log.info("✅ Knowledge Graph connected")
    except Exception as e:
        log.error("❌ Knowledge Graph connection failed", error=str(e))

    log.info("✅ All services initialisation attempt complete")
    yield
    # Shutdown
    try:
        await knowledge_graph.close()
    except Exception:
        pass
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
@app.get("/health")
async def health():
    status = "ok"
    details = {}
    
    try:
        redis = get_redis()
        await redis.ping()
        details["redis"] = "ok"
    except Exception as e:
        status = "degraded"
        details["redis"] = str(e)

    try:
        db = await get_db_pool()
        async with db.acquire() as conn:
            await conn.execute("SELECT 1")
        details["postgres"] = "ok"
    except Exception as e:
        status = "degraded"
        details["postgres"] = str(e)

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
async def start_investigation(req: InvestigationRequest, background: BackgroundTasks):
    """
    Kick off the full AEGIS investigation pipeline:
      1. Parallel agent reconnaissance (7 agents)
      2. Knowledge graph population
      3. Debate chamber (Bull / Bear / Skeptic / Synthesizer)
      4. Report generation
      5. Meta-learning update
    """
    log.info("investigation_started", id=req.investigation_id, url=req.url)
    INVESTIGATIONS_TOTAL.labels(type=req.type, status="started").inc()

    background.add_task(_run_investigation, req)
    return {"workflow_id": req.investigation_id, "status": "started"}

@app.get("/investigations/{investigation_id}/status")
async def get_status(investigation_id: str) -> InvestigationStatus:
    redis = get_redis()
    raw = await redis.get(f"inv:status:{investigation_id}")
    if not raw:
        raise HTTPException(status_code=404, detail="Investigation not found")
    import json
    data = json.loads(raw)
    return InvestigationStatus(**data)

# ─── Core Pipeline ────────────────────────────────────────────────────────────
async def _run_investigation(req: InvestigationRequest):
    inv_id = req.investigation_id
    start  = datetime.utcnow()

    async def _update_status(status: str, progress: int, agent: str = "", confidence: float = 0.0):
        import json
        await get_redis().setex(
            f"inv:status:{inv_id}", 3600,
            json.dumps({"investigation_id": inv_id, "status": status,
                        "progress": progress, "current_agent": agent, "confidence": confidence})
        )
        await publish_event(inv_id, {"type": "status_update", "status": status,
                                     "progress": progress, "agent": agent})

    try:
        # ── Mark DB running ────────────────────────────────────────────────
        db = await get_db_pool()
        async with db.acquire() as conn:
            await conn.execute(
                "UPDATE investigations SET status='running', started_at=NOW() WHERE id=$1",
                inv_id
            )

        await _update_status("running", 5, "initialising")

        # ── Phase 1: Parallel Reconnaissance ──────────────────────────────
        agents = [
            SentryAgent(llm_router, experience_bank),
            FinancialArchaeologist(llm_router, experience_bank),
            TalentFlowAgent(llm_router, experience_bank),
            TechStackAgent(llm_router, experience_bank),
            SentimentScout(llm_router, experience_bank),
            RegulatoryRadar(llm_router, experience_bank),
            CompetitiveCartographer(llm_router, experience_bank),
        ]

        await _update_status("running", 10, "reconnaissance")
        agent_tasks = [agent.investigate(inv_id, req.url) for agent in agents]
        recon_results = await asyncio.gather(*agent_tasks, return_exceptions=True)

        # Filter errors
        valid_results = []
        for i, result in enumerate(recon_results):
            if isinstance(result, Exception):
                log.error("agent_failed", agent=agents[i].name, error=str(result))
                AGENT_ERRORS.labels(agent=agents[i].name).inc()
            else:
                valid_results.append(result)

        await _update_status("running", 25, "knowledge_graph")

        # ── Phase 2: Knowledge Graph ───────────────────────────────────────
        await knowledge_graph.populate(inv_id, valid_results)
        graph_snapshot = await knowledge_graph.get_snapshot(inv_id)

        async with db.acquire() as conn:
            await conn.execute(
                """INSERT INTO knowledge_snapshots(investigation_id, snapshot_type, data)
                   VALUES($1, 'knowledge_graph', $2::jsonb)""",
                inv_id, graph_snapshot
            )

        await _update_status("running", 55, "debate_chamber")

        # ── Phase 3: Debate Chamber ────────────────────────────────────────
        debate_result = await debate_crew.run(inv_id, valid_results)

        await _update_status("running", 75, "report_generation")

        # ── Phase 4: Report Generation ────────────────────────────────────
        workflow = InvestigationWorkflow(llm_router)
        report   = await workflow.generate_report(inv_id, req.url, debate_result, valid_results)

        # ── Phase 5: Persist Report ────────────────────────────────────────
        duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
        total_tokens = sum(r.get("tokens_used", 0) for r in valid_results if isinstance(r, dict))
        cost_usd     = total_tokens * 0.000002  # ~$0.002 per 1K tokens avg

        async with db.acquire() as conn:
            await conn.execute(
                """INSERT INTO reports(
                     investigation_id, executive_summary, bull_thesis, bear_thesis,
                     skeptic_analysis, final_verdict, red_flag_matrix, moat_analysis,
                     scenarios, recommendations, raw_markdown
                   ) VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9::jsonb,$10::jsonb,$11)
                   ON CONFLICT (investigation_id) DO UPDATE SET
                     executive_summary=EXCLUDED.executive_summary,
                     bull_thesis=EXCLUDED.bull_thesis,
                     bear_thesis=EXCLUDED.bear_thesis,
                     skeptic_analysis=EXCLUDED.skeptic_analysis,
                     final_verdict=EXCLUDED.final_verdict,
                     red_flag_matrix=EXCLUDED.red_flag_matrix,
                     moat_analysis=EXCLUDED.moat_analysis,
                     scenarios=EXCLUDED.scenarios,
                     recommendations=EXCLUDED.recommendations,
                     raw_markdown=EXCLUDED.raw_markdown""",
                inv_id,
                report.get("executive_summary", ""),
                report.get("bull_thesis", ""),
                report.get("bear_thesis", ""),
                report.get("skeptic_analysis", ""),
                report.get("final_verdict", ""),
                report.get("red_flag_matrix", "[]"),
                report.get("moat_analysis", "{}"),
                report.get("scenarios", "{}"),
                report.get("recommendations", "[]"),
                report.get("raw_markdown", ""),
            )
            await conn.execute(
                """UPDATE investigations SET
                     status='completed', completed_at=NOW(),
                     confidence_score=$2, vitality_score=$3,
                     moat_score=$4, risk_score=$5,
                     company_name=$6, duration_ms=$7,
                     total_tokens=$8, total_cost_usd=$9
                   WHERE id=$1""",
                inv_id,
                report.get("confidence_score", 0.75),
                report.get("vitality_score", 70),
                report.get("moat_score", 60),
                report.get("risk_score", 30),
                report.get("company_name", ""),
                duration_ms, total_tokens, cost_usd,
            )

        await _update_status("running", 90, "meta_learning")

        # ── Phase 6: Meta-Learning Update ─────────────────────────────────
        await experience_bank.store_experience(
            investigation_id=inv_id,
            task_type=req.type,
            input_text=req.url,
            reasoning=debate_result.get("reasoning_trace", ""),
            output=report,
            outcome="success",
        )

        INVESTIGATIONS_TOTAL.labels(type=req.type, status="completed").inc()
        INVESTIGATION_DURATION.observe((datetime.utcnow() - start).total_seconds())

        await _update_status("completed", 100, "", report.get("confidence_score", 0.75))
        await publish_event(inv_id, {"type": "investigation_complete", "report": report})
        log.info("investigation_completed", id=inv_id, duration_ms=duration_ms)

    except Exception as e:
        log.error("investigation_failed", id=inv_id, error=str(e), exc_info=True)
        INVESTIGATIONS_TOTAL.labels(type=req.type, status="failed").inc()
        await _update_status("failed", 0)
        try:
            db = await get_db_pool()
            async with db.acquire() as conn:
                await conn.execute(
                    "UPDATE investigations SET status='failed' WHERE id=$1", inv_id
                )
        except Exception:
            pass


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True, log_level="info")
