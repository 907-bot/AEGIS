"""Talent Flow Agent — Leadership changes, skill shifts, hiring patterns."""
from __future__ import annotations
from agents.base_agent import BaseAgent, AgentResult
from utils.llm_router import TaskType


class TalentFlowAgent(BaseAgent):
    name      = "talent_flow"
    task_type = TaskType.SCRAPE_ANALYSIS

    SYSTEM = "You are AEGIS Talent Intelligence Agent. Analyse team, leadership, hiring patterns. Extract CEO info, co-founder backgrounds, key executives. Return ONLY valid TOON."

    async def _run(self, investigation_id: str, url: str) -> AgentResult:
        await self._emit_event(investigation_id, "in_progress", "Scanning team and leadership...")
        about_content = await self.scraper.scrape(url.rstrip("/") + "/about")
        team_content  = await self.scraper.scrape(url.rstrip("/") + "/team")
        company_content = await self.scraper.scrape(url.rstrip("/") + "/company")
        text = ""
        if about_content: text += about_content.get("text", "")[:4000]
        if team_content:  text += team_content.get("text", "")[:4000]
        if company_content: text += company_content.get("text", "")[:3000]
        if not text.strip():
            root_content = await self.scraper.scrape(url)
            if root_content:
                text = root_content.get("text", "")[:6000]

        prompt = f"""Analyse talent and leadership at {url}.
Content: {text[:8000]}

Return TOON with these exact fields:
ceo:
  name: "CEO full name"
  background: "CEO background and previous companies"
  linkedin_url: "..."
  photo_url: "..."
co_founders[1]:
  name: "Co-founder name"
  role: "Co-founder role"
  background: "previous experience"
  linkedin_url: "..."
  photo_url: "..."
leadership_team[1]:
  name: "Executive name"
  role: "title"
  background: "brief background"
  photo_url: "..."
leadership_names[1]: "CEO name"
founder_background[1]: "ex-FAANG"
team_size_estimate: "<range>"
key_skill_sets[1]: "ML"
notable_hires_signals[0]:
leadership_tenure_signals: stable|recent_changes|unknown
diversity_signals[0]:
team_quality_score: 80
office_locations[1]: "HQ city, country"
branch_offices[1]: "other locations"
red_flags[0]:
confidence: 0.8
"""

        resp = await self.llm.complete(self.task_type, self.SYSTEM, prompt, 1200, 0.3, "toon")
        data = self._extract_toon(resp.content)
        return AgentResult(agent_type=self.name, status="completed", data=data,
                           confidence=float(data.get("confidence", 0.5)),
                           evidence=[url + "/about", url + "/team"],
                           tokens_used=resp.input_tokens + resp.output_tokens)
