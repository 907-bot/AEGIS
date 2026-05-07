"""Regulatory Radar — Legal, compliance, regulatory risk detection."""
from __future__ import annotations
from agents.base_agent import BaseAgent, AgentResult
from utils.llm_router import TaskType


class RegulatoryRadar(BaseAgent):
    name      = "regulatory_radar"
    task_type = TaskType.CLASSIFICATION

    SYSTEM = "You are AEGIS Regulatory Intelligence Agent. Identify legal, compliance, and regulatory risks. Return ONLY valid JSON."

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

Return JSON:
{{
  "industry_regulations": ["SEBI", "RBI", "GDPR", "HIPAA", "PCI-DSS", "etc"],
  "compliance_signals": ["ISO27001", "SOC2", "GDPR compliant", "etc"],
  "legal_risks": ["data privacy", "regulatory approval needed", "etc"],
  "jurisdictions_operating": ["India", "USA", "EU", "etc"],
  "data_handling": "clear|vague|concerning",
  "privacy_policy_quality": "comprehensive|basic|missing",
  "terms_quality": "comprehensive|basic|missing",
  "patent_signals": ["any IP/patent mentions"],
  "litigation_signals": ["any lawsuit/legal mentions"],
  "regulatory_approval_needed": true|false,
  "regulatory_risk_level": "low|medium|high|critical",
  "compliance_score": <0-100>,
  "red_flags": ["specific regulatory red flags"],
  "confidence": <0.0-1.0>
}}"""

        resp = await self.llm.complete(self.task_type, self.SYSTEM, prompt, 800, 0.2, "json")
        data = self._extract_json(resp.content)
        return AgentResult(agent_type=self.name, status="completed", data=data,
                           confidence=float(data.get("confidence", 0.6)),
                           evidence=[url, url+"/privacy", url+"/terms"],
                           tokens_used=resp.input_tokens + resp.output_tokens)
