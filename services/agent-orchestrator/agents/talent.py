"""Talent Flow Agent — Leadership changes, skill shifts, hiring patterns."""
from __future__ import annotations
from agents.base_agent import BaseAgent, AgentResult
from utils.llm_router import TaskType


class TalentFlowAgent(BaseAgent):
    name      = "talent_flow"
    task_type = TaskType.SCRAPE_ANALYSIS

    SYSTEM = "You are AEGIS Talent Intelligence Agent. Analyse team, leadership, hiring patterns. Return ONLY valid JSON."

    async def _run(self, investigation_id: str, url: str) -> AgentResult:
        await self._emit_event(investigation_id, "in_progress", "Scanning team and leadership...")
        about_content = await self.scraper.scrape(url.rstrip("/") + "/about")
        team_content  = await self.scraper.scrape(url.rstrip("/") + "/team")
        text = ""
        if about_content: text += about_content.get("text", "")[:4000]
        if team_content:  text += team_content.get("text", "")[:4000]

        prompt = f"""Analyse talent and leadership at {url}.
Content: {text[:6000]}

Return JSON:
{{
  "leadership_names": ["CEO name", "CTO name", ...],
  "founder_background": ["academic", "ex-FAANG", "serial-entrepreneur", "domain-expert"],
  "team_size_estimate": "<range>",
  "key_skill_sets": ["ML", "fintech", "healthcare", ...],
  "notable_hires_signals": ["any notable recent hires mentioned"],
  "leadership_tenure_signals": "stable|recent_changes|unknown",
  "diversity_signals": ["any observable signals"],
  "team_quality_score": <0-100>,
  "red_flags": ["any concerning team signals"],
  "confidence": <0.0-1.0>
}}"""

        resp = await self.llm.complete(self.task_type, self.SYSTEM, prompt, 800, 0.3, "json")
        data = self._extract_json(resp.content)
        return AgentResult(agent_type=self.name, status="completed", data=data,
                           confidence=float(data.get("confidence", 0.5)),
                           evidence=[url + "/about", url + "/team"],
                           tokens_used=resp.input_tokens + resp.output_tokens)
