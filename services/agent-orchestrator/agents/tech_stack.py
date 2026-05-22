"""TechStack Agent — Deep technology analysis from GitHub, job descriptions, DNS."""
from __future__ import annotations
from agents.base_agent import BaseAgent, AgentResult
from utils.llm_router import TaskType


class TechStackAgent(BaseAgent):
    name      = "tech_stack"
    task_type = TaskType.SCRAPE_ANALYSIS

    SYSTEM = "You are AEGIS Tech Stack Intelligence Agent. Infer technology decisions from observable signals. Return ONLY valid TOON."

    async def _run(self, investigation_id: str, url: str) -> AgentResult:
        await self._emit_event(investigation_id, "in_progress", "Analysing technology stack...")
        content = await self.scraper.scrape(url)
        text = content.get("text", "") if content else ""
        html = content.get("html", "") if content else ""

        prompt = f"""Analyse technology stack at {url}.
HTML signals (first 5000 chars): {html[:5000]}
Text content: {text[:3000]}

Return TOON:
frontend[1]: "React"
backend_inference[1]: "Python"
infrastructure[1]: "Vercel"
databases_inferred[1]: "PostgreSQL"
ai_ml_signals[1]: "OpenAI"
monitoring[1]: "Sentry"
payments[1]: "Stripe"
security_signals[1]: "SOC2"
api_type: REST|GraphQL|gRPC|unknown
mobile_presence: iOS|Android|both|none
tech_maturity: prototype|startup|scale-up|enterprise
tech_debt_signals[0]:
innovation_score: 80
confidence: 0.8
"""

        resp = await self.llm.complete(self.task_type, self.SYSTEM, prompt, 800, 0.2, "toon")
        data = self._extract_toon(resp.content)
        return AgentResult(agent_type=self.name, status="completed", data=data,
                           confidence=float(data.get("confidence", 0.55)),
                           evidence=[url], tokens_used=resp.input_tokens + resp.output_tokens)
