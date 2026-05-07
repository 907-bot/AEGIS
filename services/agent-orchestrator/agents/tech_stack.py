"""TechStack Agent — Deep technology analysis from GitHub, job descriptions, DNS."""
from __future__ import annotations
from agents.base_agent import BaseAgent, AgentResult
from utils.llm_router import TaskType


class TechStackAgent(BaseAgent):
    name      = "tech_stack"
    task_type = TaskType.SCRAPE_ANALYSIS

    SYSTEM = "You are AEGIS Tech Stack Intelligence Agent. Infer technology decisions from observable signals. Return ONLY valid JSON."

    async def _run(self, investigation_id: str, url: str) -> AgentResult:
        await self._emit_event(investigation_id, "in_progress", "Analysing technology stack...")
        content = await self.scraper.scrape(url)
        text = content.get("text", "") if content else ""
        html = content.get("html", "") if content else ""

        prompt = f"""Analyse technology stack at {url}.
HTML signals (first 5000 chars): {html[:5000]}
Text content: {text[:3000]}

Return JSON:
{{
  "frontend": ["React", "Vue", "etc"],
  "backend_inference": ["Python", "Node.js", "Go", "etc"],
  "infrastructure": ["AWS", "GCP", "Azure", "Vercel", "etc"],
  "databases_inferred": ["PostgreSQL", "MongoDB", "etc"],
  "ai_ml_signals": ["OpenAI", "HuggingFace", "PyTorch", "etc"],
  "monitoring": ["Datadog", "Sentry", "etc"],
  "payments": ["Stripe", "Razorpay", "etc"],
  "security_signals": ["SOC2", "ISO27001", "GDPR", "etc"],
  "api_type": "REST|GraphQL|gRPC|unknown",
  "mobile_presence": "iOS|Android|both|none",
  "tech_maturity": "prototype|startup|scale-up|enterprise",
  "tech_debt_signals": ["any observable signals"],
  "innovation_score": <0-100>,
  "confidence": <0.0-1.0>
}}"""

        resp = await self.llm.complete(self.task_type, self.SYSTEM, prompt, 800, 0.2, "json")
        data = self._extract_json(resp.content)
        return AgentResult(agent_type=self.name, status="completed", data=data,
                           confidence=float(data.get("confidence", 0.55)),
                           evidence=[url], tokens_used=resp.input_tokens + resp.output_tokens)
