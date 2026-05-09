"""
AEGIS Base Agent — Shared superclass for all 7 specialized agents.
Handles: ethical scraping, few-shot retrieval, telemetry, retry logic.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import structlog
from cachetools import TTLCache
from tenacity import retry, stop_after_attempt, wait_exponential

from utils.llm_router import LLMRouter, TaskType, LLMResponse
from utils.redis_client import get_redis, publish_event

log = structlog.get_logger()


@dataclass
class AgentResult:
    agent_type:    str
    status:        str           # started | completed | failed | timeout
    data:          dict          = field(default_factory=dict)
    confidence:    float         = 0.0
    evidence:      list[str]     = field(default_factory=list)
    tokens_used:   int           = 0
    latency_ms:    int           = 0
    error:         Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "agent_type":  self.agent_type,
            "status":      self.status,
            "data":        self.data,
            "confidence":  self.confidence,
            "evidence":    self.evidence,
            "tokens_used": self.tokens_used,
            "latency_ms":  self.latency_ms,
        }


class EthicalScraper:
    """Playwright-based ethical scraper with robots.txt + rate limiting."""

    _semaphore = asyncio.Semaphore(2)  # Limit concurrent browser launches

    def __init__(self):
        self.robots_cache: TTLCache = TTLCache(maxsize=500, ttl=3600)
        self.rate_limit_delay = 2.0  # seconds between requests per domain
        self._domain_last_req: dict[str, float] = {}
        self.user_agent = "AegisBot/1.0 (Research Intelligence; contact@aegis.ai)"

    async def scrape(self, url: str, investigation_id: Optional[str] = None) -> Optional[dict]:
        async with self._semaphore:
            domain = urlparse(url).netloc
            if investigation_id:
                await publish_event(investigation_id, {
                    "type": "agent_event",
                    "investigationId": investigation_id,
                    "agentType": "system",
                    "status": "scraping",
                    "currentAction": f"Launching browser for {domain}...",
                    "timestamp": datetime.utcnow().isoformat(),
                })

            # Robots.txt check
            if not await self._check_robots(domain, url):
                log.warning("blocked_by_robots", url=url)
                return None

            # Rate limiting per domain
            elapsed = time.time() - self._domain_last_req.get(domain, 0)
            if elapsed < self.rate_limit_delay:
                await asyncio.sleep(self.rate_limit_delay - elapsed)
            self._domain_last_req[domain] = time.time()

            try:
                from playwright.async_api import async_playwright
                async with async_playwright() as pw:
                    browser = await pw.chromium.launch(
                        headless=True,
                        args=["--no-sandbox", "--disable-dev-shm-usage"]
                    )
                    ctx = await browser.new_context(
                        user_agent=self.user_agent,
                        viewport={"width": 1920, "height": 1080},
                    )
                    # Block heavy assets for speed
                    await ctx.route(
                        "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,mp4,mp3}",
                        lambda r: r.abort()
                    )
                    page = await ctx.new_page()
                    # Increase timeout and use a more reliable wait_until
                    resp = await page.goto(url, wait_until="networkidle", timeout=45000)
                    if resp and resp.status >= 400:
                        await browser.close()
                        return None

                    html  = await page.content()
                    text  = await page.inner_text("body")
                    title = await page.title()
                    await browser.close()

                    return {
                        "url":         url,
                        "html":        html[:50000],  # cap size
                        "text":        text[:20000],
                        "title":       title,
                        "scraped_at":  datetime.utcnow().isoformat(),
                        "status_code": resp.status if resp else 200,
                    }
            except Exception as e:
                log.error("scraping_failed", url=url, error=str(e))
                return None

    async def _check_robots(self, domain: str, url: str) -> bool:
        if domain in self.robots_cache:
            return self.robots_cache[domain].can_fetch(self.user_agent, url)
        try:
            import httpx
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{domain}/robots.txt"
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(robots_url)
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.parse(r.text.splitlines())
            self.robots_cache[domain] = rp
            return rp.can_fetch(self.user_agent, url)
        except Exception:
            return True  # Allow on error


class BaseAgent(ABC):
    """Abstract base for all AEGIS agents."""

    name: str = "base_agent"
    task_type: TaskType = TaskType.SCRAPE_ANALYSIS

    def __init__(self, llm_router: LLMRouter, experience_bank: Any = None):
        self.llm            = llm_router
        self.experience_bank = experience_bank
        self.scraper        = EthicalScraper()

    async def investigate(self, investigation_id: str, url: str) -> dict:
        start = time.monotonic()
        await self._emit_event(investigation_id, "started", f"Agent {self.name} starting...")

        try:
            result = await asyncio.wait_for(
                self._run(investigation_id, url),
                timeout=90.0
            )
            latency = int((time.monotonic() - start) * 1000)

            await self._emit_event(
                investigation_id, "completed",
                f"{self.name} finished",
                confidence=result.confidence,
                evidence_count=len(result.evidence),
                latency_ms=latency,
            )
            return result.to_dict()

        except asyncio.TimeoutError:
            log.warning("agent_timeout", agent=self.name, investigation_id=investigation_id)
            await self._emit_event(investigation_id, "timeout", f"{self.name} timed out")
            return AgentResult(agent_type=self.name, status="timeout").to_dict()

        except Exception as exc:
            log.error("agent_error", agent=self.name, error=str(exc), exc_info=True)
            await self._emit_event(investigation_id, "failed", str(exc))
            return AgentResult(agent_type=self.name, status="failed", error=str(exc)).to_dict()

    @abstractmethod
    async def _run(self, investigation_id: str, url: str) -> AgentResult:
        """Subclasses implement this."""
        ...

    async def _few_shot_prompt(self, task_description: str, context: str) -> str:
        """Fetch few-shot examples from experience bank and inject."""
        examples_block = ""
        if self.experience_bank:
            try:
                examples = await self.experience_bank.retrieve_similar(
                    input_text=f"{self.name}:{context[:500]}",
                    task_type=self.name,
                    k=3,
                )
                if examples:
                    examples_block = "\n\n## Similar Past Analyses (Few-Shot):\n"
                    for ex in examples:
                        examples_block += f"\n**Example** (confidence: {ex.get('confidence',0):.2f}):\n"
                        examples_block += f"Input: {ex.get('input_text','')[:300]}\n"
                        examples_block += f"Output: {json.dumps(ex.get('output',{}))[:500]}\n---"
            except Exception:
                pass
        return examples_block

    async def _emit_event(
        self, investigation_id: str, event_type: str, action: str,
        confidence: float = 0.0, evidence_count: int = 0, latency_ms: int = 0,
    ):
        try:
            await publish_event(investigation_id, {
                "type":            "agent_event",
                "investigationId": investigation_id,
                "agentType":       self.name,
                "status":          event_type,
                "currentAction":   action,
                "confidence":      confidence,
                "evidenceCount":   evidence_count,
                "latencyMs":       latency_ms,
                "timestamp":       datetime.utcnow().isoformat(),
            })
            # Also log to DB
            redis = get_redis()
            await redis.lpush(
                f"agent_logs:{investigation_id}",
                json.dumps({
                    "agent_type":    self.name,
                    "event_type":    event_type,
                    "current_action": action,
                    "confidence":    confidence,
                    "evidence_count": evidence_count,
                    "latency_ms":    latency_ms,
                    "created_at":    datetime.utcnow().isoformat(),
                })
            )
        except Exception:
            pass

    def _extract_json(self, text: str) -> dict:
        """Safely extract JSON from LLM output."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON block
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
        return {}

    def _confidence_from_evidence(self, evidence: list[str]) -> float:
        """Heuristic confidence based on evidence count."""
        if not evidence:
            return 0.3
        n = len(evidence)
        return min(0.95, 0.4 + (n * 0.08))
