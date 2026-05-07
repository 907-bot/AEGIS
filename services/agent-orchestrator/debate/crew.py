"""
AEGIS Debate Chamber — Bull vs Bear vs Skeptic → Synthesizer
Uses CrewAI for multi-agent adversarial debate.
"""
from __future__ import annotations

import json
import re
from typing import Any

import structlog

from utils.llm_router import LLMRouter, TaskType

log = structlog.get_logger()


class AegisDebateCrew:
    """
    Four-agent debate:
      1. Bull Agent    — argues growth potential
      2. Bear Agent    — identifies risks & threats
      3. Skeptic Agent — audits reasoning chains, detects fallacies
      4. Synthesizer   — resolves conflicts with confidence intervals
    """

    def __init__(self, llm_router: LLMRouter):
        self.llm = llm_router

    async def run(self, investigation_id: str, recon_results: list[dict]) -> dict:
        """Run the full debate pipeline and return synthesis."""
        context = self._build_context(recon_results)

        log.info("debate_started", investigation_id=investigation_id)

        # ── Round 1: Bull & Bear run in parallel ──────────────────────────
        bull_resp, bear_resp = await asyncio.gather(
            self._bull_agent(context),
            self._bear_agent(context),
        )
        # ── Round 2: Skeptic audits both ──────────────────────────────────
        skeptic_resp = await self._skeptic_agent(context, bull_resp, bear_resp)
        # ── Round 3: Synthesizer resolves ─────────────────────────────────
        synthesis = await self._synthesizer_agent(context, bull_resp, bear_resp, skeptic_resp)

        return {
            "bull_thesis":       bull_resp,
            "bear_thesis":       bear_resp,
            "skeptic_analysis":  skeptic_resp,
            "synthesis":         synthesis,
            "reasoning_trace":   f"Bull→Bear→Skeptic→Synthesizer debate completed",
            **synthesis,
        }

    # ─── Bull Agent ───────────────────────────────────────────────────────
    async def _bull_agent(self, context: str) -> str:
        system = """You are the AEGIS Bull Agent — a seasoned VC partner who argues for growth potential.
Your role: make the strongest possible case for WHY this company will succeed.
Focus on: market opportunity, competitive advantages, growth signals, team strength, moat.
Be specific, evidence-based, but optimistic. Avoid wishful thinking without substance."""

        prompt = f"""Company Intelligence Context:
{context}

Present the BULL CASE in structured format:
1. Core Investment Thesis (2-3 sentences)
2. Top 5 Growth Catalysts (with evidence from data)
3. Competitive Moat Analysis (why they can win long-term)
4. Market Timing (why NOW is the right time)
5. Team Strength Assessment
6. Bull Score: XX/100 with confidence interval XX-XX%"""

        resp = await self.llm.complete(TaskType.DEBATE, system, prompt, 1500, 0.7)
        return resp.content

    # ─── Bear Agent ───────────────────────────────────────────────────────
    async def _bear_agent(self, context: str) -> str:
        system = """You are the AEGIS Bear Agent — a forensic accountant and risk analyst.
Your role: make the strongest possible case for WHY this company could fail or underperform.
Focus on: financial risks, competitive threats, regulatory exposure, execution challenges, market risks.
Be specific, evidence-based, and unflinchingly honest about risks."""

        prompt = f"""Company Intelligence Context:
{context}

Present the BEAR CASE in structured format:
1. Core Risk Thesis (2-3 sentences)
2. Top 5 Red Flags (with evidence from data)
3. Competitive Threats Assessment (who can disrupt them)
4. Financial Risk Analysis (burn rate, funding risk, unit economics)
5. Execution Risk Factors
6. Bear Score: XX/100 risk level with specific scenarios"""

        resp = await self.llm.complete(TaskType.DEBATE, system, prompt, 1500, 0.7)
        return resp.content

    # ─── Skeptic Agent ────────────────────────────────────────────────────
    async def _skeptic_agent(self, context: str, bull: str, bear: str) -> str:
        system = """You are the AEGIS Skeptic Agent — a meta-cognitive auditor.
Your role: audit the reasoning quality of both Bull and Bear arguments.
You detect: logical fallacies, unsupported assumptions, cognitive biases, hallucinations,
overconfidence, correlation-causation confusion, survivorship bias, recency bias.
You do NOT argue for or against — you evaluate the quality of reasoning itself."""

        prompt = f"""Review these two analyses:

=== BULL CASE ===
{bull}

=== BEAR CASE ===
{bear}

=== ORIGINAL EVIDENCE ===
{context[:3000]}

Skeptic Audit:
1. Bull Argument Quality
   - Well-supported claims (list)
   - Unsupported assumptions (list)
   - Cognitive biases detected (list)
   - Overconfidence score: X/10

2. Bear Argument Quality
   - Well-supported claims (list)
   - Unsupported assumptions (list)
   - Cognitive biases detected (list)
   - Overconfidence score: X/10

3. Contradictions between Bull and Bear
4. Missing perspectives neither addressed
5. Evidence gaps (what data would change the analysis)
6. Overall reliability score for this analysis: XX%"""

        resp = await self.llm.complete(TaskType.CRITIQUE, system, prompt, 1500, 0.5)
        return resp.content

    # ─── Synthesizer Agent ────────────────────────────────────────────────
    async def _synthesizer_agent(self, context: str, bull: str, bear: str, skeptic: str) -> dict:
        system = """You are the AEGIS Chief Strategist — a McKinsey Partner who synthesizes
multi-perspective intelligence into actionable strategic verdicts.
You weigh evidence quality, resolve contradictions, and produce calibrated recommendations.
Return ONLY valid JSON."""

        prompt = f"""Synthesize this four-agent analysis:

BULL CASE: {bull[:2000]}
BEAR CASE: {bear[:2000]}
SKEPTIC AUDIT: {skeptic[:1500]}
EVIDENCE: {context[:2000]}

Return JSON synthesis:
{{
  "final_verdict": "strong_buy|buy|hold|watch|avoid",
  "executive_summary": "<3-4 sentence summary of the complete picture>",
  "confidence_score": <0.0-1.0>,
  "vitality_score": <0-100>,
  "moat_score": <0-100>,
  "risk_score": <0-100>,
  "company_name": "<extracted company name>",
  "bull_thesis": "<condensed bull case, 2-3 sentences>",
  "bear_thesis": "<condensed bear case, 2-3 sentences>",
  "skeptic_analysis": "<key audit findings, 2-3 sentences>",
  "red_flag_matrix": [
    {{"flag": "...", "severity": "low|medium|high|critical", "category": "financial|operational|regulatory|competitive"}}
  ],
  "moat_analysis": {{
    "primary_moat": "network_effects|switching_costs|cost_advantage|brand|ip|none",
    "moat_strength": "wide|narrow|none",
    "durability_years": <estimate>,
    "threats": ["..."]
  }},
  "scenarios": {{
    "bull": {{"probability": 0.3, "outcome": "...", "trigger": "..."}},
    "base": {{"probability": 0.5, "outcome": "...", "trigger": "..."}},
    "bear": {{"probability": 0.2, "outcome": "...", "trigger": "..."}}
  }},
  "recommendations": [
    {{"action": "...", "rationale": "...", "priority": "immediate|short_term|long_term"}}
  ],
  "comparable_companies": ["..."],
  "next_monitoring_triggers": ["what to watch for"]
}}"""

        resp = await self.llm.complete(TaskType.SYNTHESIS, system, prompt, 2000, 0.4, "json")
        data = self._extract_json(resp.content)
        return data

    def _build_context(self, results: list[dict]) -> str:
        parts = []
        for r in results:
            if r.get("status") == "completed":
                parts.append(f"=== {r['agent_type'].upper()} ===\n{json.dumps(r.get('data', {}), indent=2)[:1500]}")
        return "\n\n".join(parts)

    def _extract_json(self, text: str) -> dict:
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
        return {"error": "synthesis_parse_failed", "raw": text[:500]}


import asyncio  # noqa: E402 (needed for gather in class methods)
