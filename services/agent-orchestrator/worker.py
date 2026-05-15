"""
AEGIS ARQ Worker — runs investigations as background jobs.

Start with: arq worker.WorkerSettings
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
import redis.asyncio as aioredis
from arq import create_pool
from arq.connections import RedisSettings
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
from utils.llm_router import LLMRouter
from utils.metrics import INVESTIGATIONS_TOTAL, INVESTIGATION_DURATION, AGENT_ERRORS

logger = logging.getLogger("aegis.worker")

# ─── Environment ─────────────────────────────────────────────────────────────
REDIS_URL = os.environ["REDIS_URL"]
DATABASE_URL = os.environ["DATABASE_URL"]


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def update_investigation(db: asyncpg.Connection, investigation_id: str, **fields):
    """Update any columns on the investigations table."""
    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(fields))
    values = list(fields.values())
    await db.execute(
        f"UPDATE investigations SET {set_clause} WHERE id = $1",
        investigation_id, *values
    )


async def publish_event(redis: aioredis.Redis, investigation_id: str, event: dict):
    """Publish a progress event so the Go gateway streams it to the frontend."""
    channel = f"investigation:{investigation_id}:events"
    await redis.publish(channel, json.dumps({
        **event,
        "investigation_id": investigation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))


async def update_status(
    redis: aioredis.Redis,
    investigation_id: str,
    status: str,
    progress: int,
    agent: str = "",
    confidence: float = 0.0,
):
    """Update investigation status in Redis."""
    await redis.setex(
        f"inv:status:{investigation_id}", 3600,
        json.dumps({
            "investigation_id": investigation_id,
            "status": status,
            "progress": progress,
            "current_agent": agent,
            "confidence": confidence,
        })
    )
    await publish_event(redis, investigation_id, {
        "type": "status_update",
        "status": status,
        "progress": progress,
        "agent": agent,
    })


# ─── Main Investigation Task ──────────────────────────────────────────────────

async def run_investigation(
    ctx: dict,
    investigation_id: str,
    url: str,
    investigation_type: str = "competitive",
    user_id: str = "demo-user",
    strategy_config: dict = None,
):
    """
    ARQ task: Runs the full AEGIS investigation pipeline.
    ctx["db"] — asyncpg connection
    ctx["redis"] — aioredis client
    """
    db: asyncpg.Connection = ctx["db"]
    redis: aioredis.Redis = ctx["redis"]

    start = datetime.utcnow()
    logger.info(f"[{investigation_id}] Starting investigation: {url}")

    try:
        # Mark DB running
        await update_investigation(
            db, investigation_id,
            status="running",
            started_at=datetime.now(timezone.utc)
        )
        await update_status(redis, investigation_id, "running", 5, "initialising")

        # Initialize services
        llm_router = LLMRouter()
        experience_bank = ExperienceBank()
        knowledge_graph = KnowledgeGraphService()
        debate_crew = AegisDebateCrew(llm_router)

        try:
            await knowledge_graph.connect()
        except Exception as e:
            logger.warning(f"[{investigation_id}] Knowledge graph connection failed: {e}")

        INVESTIGATIONS_TOTAL.labels(type=investigation_type, status="started").inc()

        # ── Phase 1: Parallel Reconnaissance ──────────────────────────────
        await update_status(redis, investigation_id, "running", 10, "reconnaissance")

        agents = [
            SentryAgent(llm_router, experience_bank),
            FinancialArchaeologist(llm_router, experience_bank),
            TalentFlowAgent(llm_router, experience_bank),
            TechStackAgent(llm_router, experience_bank),
            SentimentScout(llm_router, experience_bank),
            RegulatoryRadar(llm_router, experience_bank),
            CompetitiveCartographer(llm_router, experience_bank),
        ]

        agent_tasks = [agent.investigate(investigation_id, url) for agent in agents]
        recon_results = await asyncio.gather(*agent_tasks, return_exceptions=True)

        # Filter errors
        valid_results = []
        for i, result in enumerate(recon_results):
            if isinstance(result, Exception):
                logger.error(f"[{investigation_id}] Agent {agents[i].name} failed: {result}")
                AGENT_ERRORS.labels(agent=agents[i].name).inc()
            else:
                valid_results.append(result)

        await update_status(redis, investigation_id, "running", 25, "knowledge_graph")

        # ── Phase 2: Knowledge Graph ───────────────────────────────────────
        try:
            await knowledge_graph.populate(investigation_id, valid_results)
            graph_snapshot = await knowledge_graph.get_snapshot(investigation_id)
            await db.execute(
                """INSERT INTO knowledge_snapshots(investigation_id, snapshot_type, data)
                   VALUES($1, 'knowledge_graph', $2::jsonb)""",
                investigation_id, graph_snapshot
            )
        except Exception as e:
            logger.warning(f"[{investigation_id}] Knowledge graph population failed: {e}")

        await update_status(redis, investigation_id, "running", 55, "debate_chamber")

        # ── Phase 3: Debate Chamber ────────────────────────────────────────
        debate_result = await debate_crew.run(investigation_id, valid_results)

        await update_status(redis, investigation_id, "running", 75, "report_generation")

        # ── Phase 4: Report Generation ────────────────────────────────────
        workflow = InvestigationWorkflow(llm_router)
        report = await workflow.generate_report(investigation_id, url, debate_result, valid_results)

        # ── Phase 5: Persist Report ────────────────────────────────────────
        duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
        total_tokens = sum(r.get("tokens_used", 0) for r in valid_results if isinstance(r, dict))
        cost_usd = total_tokens * 0.000002  # ~$0.002 per 1K tokens avg

        await db.execute(
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
            investigation_id,
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

        await update_investigation(
            db, investigation_id,
            status="completed",
            completed_at=datetime.now(timezone.utc),
            confidence_score=report.get("confidence_score", 0.75),
            vitality_score=report.get("vitality_score", 70),
            moat_score=report.get("moat_score", 60),
            risk_score=report.get("risk_score", 30),
            company_name=report.get("company_name", ""),
            duration_ms=duration_ms,
            total_tokens=total_tokens,
            total_cost_usd=cost_usd,
        )

        await update_status(redis, investigation_id, "running", 90, "meta_learning")

        # ── Phase 6: Meta-Learning Update ─────────────────────────────────
        await experience_bank.store_experience(
            investigation_id=investigation_id,
            task_type=investigation_type,
            input_text=url,
            reasoning=debate_result.get("reasoning_trace", ""),
            output=report,
            outcome="success",
        )

        INVESTIGATIONS_TOTAL.labels(type=investigation_type, status="completed").inc()
        INVESTIGATION_DURATION.observe((datetime.utcnow() - start).total_seconds())

        await update_status(redis, investigation_id, "completed", 100, "", report.get("confidence_score", 0.75))
        await publish_event(redis, investigation_id, {"type": "investigation_complete", "report": report})

        logger.info(f"[{investigation_id}] Investigation complete. Duration: {duration_ms}ms")

        # Cleanup
        try:
            await knowledge_graph.close()
        except Exception:
            pass

        return {"investigation_id": investigation_id, "status": "completed"}

    except Exception as e:
        err = traceback.format_exc()
        logger.error(f"[{investigation_id}] Investigation failed: {e}\n{err}")
        INVESTIGATIONS_TOTAL.labels(type=investigation_type, status="failed").inc()

        await update_status(redis, investigation_id, "failed", 0)
        await update_investigation(db, investigation_id, status="failed")

        try:
            await knowledge_graph.close()
        except Exception:
            pass

        raise


# ─── ARQ Lifecycle Hooks ─────────────────────────────────────────────────────

async def startup(ctx: dict):
    """Called once when the ARQ worker boots. Set up shared DB + Redis."""
    ctx["db"] = await asyncpg.connect(DATABASE_URL)
    ctx["redis"] = aioredis.from_url(REDIS_URL, decode_responses=True)
    logger.info("✅ ARQ Worker started — DB and Redis connected")


async def shutdown(ctx: dict):
    """Clean up on worker shutdown."""
    await ctx["db"].close()
    await ctx["redis"].aclose()
    logger.info("👋 ARQ Worker shut down cleanly")


# ─── Worker Settings ─────────────────────────────────────────────────────────

class WorkerSettings:
    """
    ARQ reads this class to configure the worker.
    Run with: arq worker.WorkerSettings
    """
    functions = [run_investigation]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 5                      # concurrent investigations
    job_timeout = 600                 # 10 min max per investigation
    keep_result = 3600                # keep result in Redis for 1h

    @property
    def redis_settings(self):
        return RedisSettings.from_dsn(REDIS_URL)
