"""Regulatory Radar — Legal, compliance, regulatory risk detection."""
from __future__ import annotations
from agents.base_agent import BaseAgent, AgentResult
from utils.llm_router import TaskType


class RegulatoryRadar(BaseAgent):
    name      = "regulatory_radar"
    task_type = TaskType.CLASSIFICATION
    # Regulatory scanning can be longer due to multiple policy pages
    timeout_seconds = 150
    max_attempts = 2

    SYSTEM = "You are AEGIS Regulatory Intelligence Agent. Identify legal, compliance, and regulatory risks. Return ONLY valid TOON."

    async def _run(self, investigation_id: str, url: str) -> AgentResult:
        await self._emit_event(investigation_id, "in_progress", "Scanning regulatory signals...")
        content   = await self.scraper.scrape(url)
        privacy   = await self.scraper.scrape(url.rstrip("/") + "/privacy")
        terms     = await self.scraper.scrape(url.rstrip("/") + "/terms")

        text = ""
        if content: text += content.get("text", "")[:3000]
        if privacy: text += privacy.get("text", "")[:2000]
        if terms:   text += terms.get("text", "")[:2000]

        prompt = f"""Analyse regulatory and compliance landscape for {url}.
Content: {text}

Return TOON:
industry_regulations[1]: "SEBI"
compliance_signals[1]: "ISO27001"
legal_risks[1]: "data privacy"
jurisdictions_operating[1]: "India"
data_handling: clear|vague|concerning
privacy_policy_quality: comprehensive|basic|missing
terms_quality: comprehensive|basic|missing
patent_signals[0]:
litigation_signals[0]:
regulatory_approval_needed: true|false
regulatory_risk_level: low|medium|high|critical
compliance_score: 85
red_flags[0]:
confidence: 0.8
"""

        resp = await self.llm.complete(self.task_type, self.SYSTEM, prompt, 800, 0.2, "toon")
        data = self._extract_toon(resp.content)
        return AgentResult(agent_type=self.name, status="completed", data=data,
                           confidence=float(data.get("confidence", 0.6)),
                           evidence=[url, url+"/privacy", url+"/terms"],
                           tokens_used=resp.input_tokens + resp.output_tokens)
