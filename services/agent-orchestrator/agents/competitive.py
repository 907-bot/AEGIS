"""Competitive Cartographer — Maps the competitive landscape."""
from __future__ import annotations
from agents.base_agent import BaseAgent, AgentResult
from utils.llm_router import TaskType


class CompetitiveCartographer(BaseAgent):
    name      = "competitive_cartographer"
    task_type = TaskType.CLASSIFICATION

    SYSTEM = """You are AEGIS Competitive Intelligence Agent. Map the competitive landscape with precision.
Identify direct competitors, indirect threats, market positioning, and moat strength. Return ONLY valid JSON."""

    async def _run(self, investigation_id: str, url: str) -> AgentResult:
        await self._emit_event(investigation_id, "in_progress", "Mapping competitive landscape...")
        content = await self.scraper.scrape(url)
        text = content.get("text", "")[:6000] if content else ""

        few_shot = await self._few_shot_prompt("competitive_analysis", text[:500])
        prompt = f"""Map the competitive landscape for {url}.
Website Content: {text}
{few_shot}

Return JSON:
{{
  "direct_competitors": [
    {{"name": "...", "url": "...", "similarity": <0-100>, "threat_level": "low|medium|high"}}
  ],
  "indirect_competitors": ["..."],
  "market_position": "leader|challenger|niche|newcomer",
  "differentiation": ["key differentiators"],
  "competitive_moat": {{
    "type": "network_effects|switching_costs|cost_advantage|intangible_assets|none",
    "strength": "wide|narrow|none",
    "durability": "durable|fragile|unknown"
  }},
  "market_size_estimate": "micro|niche|medium|large|massive",
  "market_maturity": "emerging|growing|mature|declining",
  "winner_take_all": true|false,
  "barriers_to_entry": ["capital", "regulation", "network effects", "etc"],
  "substitution_risk": "low|medium|high",
  "moat_score": <0-100>,
  "competitive_risk_score": <0-100>,
  "confidence": <0.0-1.0>
}}"""

        resp = await self.llm.complete(self.task_type, self.SYSTEM, prompt, 1000, 0.4, "json")
        data = self._extract_json(resp.content)
        return AgentResult(agent_type=self.name, status="completed", data=data,
                           confidence=float(data.get("confidence", 0.55)),
                           evidence=[url], tokens_used=resp.input_tokens + resp.output_tokens)
