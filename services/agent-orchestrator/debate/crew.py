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
Be specific, evidence-based, but optimistic. Avoid wishful thinking without substance.
Include specific metrics, comparable companies, and quantified projections where possible."""

        prompt = f"""Company Intelligence Context:
{context}

Present the BULL CASE in detailed structured format:
1. Core Investment Thesis (3-4 sentences with clear reasoning chain)
2. Top 7 Growth Catalysts (each with: catalyst description, evidence from data, estimated revenue impact, timeline)
3. Total Addressable Market (TAM) Assessment (market size, growth rate, company's share potential)
4. Competitive Moat Analysis (primary moat type, strength, durability, specific advantages over each competitor)
5. Market Timing Analysis (why NOW is the right time, market tailwinds, regulatory tailwinds, technology shifts)
6. Team & Talent Assessment (leadership strengths, hiring velocity, key hires, cultural advantages)
7. Product/Technology Differentiation (unique tech, IP, data moats, R&D pipeline)
8. Bull Score: XX/100 with confidence interval XX-XX%
9. Price Target Scenarios (bull: XX, base: XX, bear: XX)"""

        resp = await self.llm.complete(TaskType.DEBATE, system, prompt, 2000, 0.7)
        return resp.content

    # ─── Bear Agent ───────────────────────────────────────────────────────
    async def _bear_agent(self, context: str) -> str:
        system = """You are the AEGIS Bear Agent — a forensic accountant and risk analyst.
Your role: make the strongest possible case for WHY this company could fail or underperform.
Focus on: financial risks, competitive threats, regulatory exposure, execution challenges, market risks.
Be specific, evidence-based, and unflinchingly honest about risks.
Include specific numbers, timelines, and worst-case scenarios where possible."""

        prompt = f"""Company Intelligence Context:
{context}

Present the BEAR CASE in detailed structured format:
1. Core Risk Thesis (3-4 sentences with clear risk chain)
2. Top 7 Red Flags (each with: flag description, severity, evidence, potential impact, likelihood)
3. Competitive Threat Analysis (direct competitors, indirect disruptors, new entrants, substitute technologies)
4. Financial Risk Breakdown (burn rate analysis, funding runway, unit economics, margin pressure, debt covenants)
5. Regulatory & Legal Risks (current/pending regulations, lawsuits, compliance costs, geopolitical risks)
6. Execution Risk Factors (management gaps, technical debt, scaling challenges, attrition risk)
7. Market & Macro Risks (market saturation, economic downturn, changing consumer behavior, technology obsolescence)
8. Bear Score: XX/100 risk level with confidence interval
9. Worst-Case Scenario Analysis (what failure looks like, timeline, triggers)"""

        resp = await self.llm.complete(TaskType.DEBATE, system, prompt, 2000, 0.7)
        return resp.content

    # ─── Skeptic Agent ────────────────────────────────────────────────────
    async def _skeptic_agent(self, context: str, bull: str, bear: str) -> str:
        system = """You are the AEGIS Skeptic Agent — a meta-cognitive auditor.
Your role: audit the reasoning quality of both Bull and Bear arguments.
You detect: logical fallacies, unsupported assumptions, cognitive biases, hallucinations,
overconfidence, correlation-causation confusion, survivorship bias, recency bias.
You do NOT argue for or against — you evaluate the quality of reasoning itself.
Provide specific examples from each argument and rate each claim."""

        prompt = f"""Review these two analyses:

=== BULL CASE ===
{bull}

=== BEAR CASE ===
{bear}

=== ORIGINAL EVIDENCE ===
{context[:4000]}

Skeptic Audit:
1. Bull Argument Quality
   - Well-supported claims (list each with evidence reference)
   - Unsupported assumptions (list each with why unsupported)
   - Cognitive biases detected (list each with example quote)
   - Factual errors or hallucinations (list each with correction)
   - Overconfidence score: X/10

2. Bear Argument Quality
   - Well-supported claims (list each with evidence reference)
   - Unsupported assumptions (list each with why unsupported)
   - Cognitive biases detected (list each with example quote)
   - Factual errors or hallucinations (list each with correction)
   - Overconfidence score: X/10

3. Contradictions between Bull and Bear (list each with resolution attempted)
4. Missing perspectives neither addressed (what angles were ignored)
5. Evidence quality assessment (what data is strong, weak, or missing)
6. Key questions that would change the analysis (top 3 questions)
7. Overall reliability score for this analysis: XX% (with justification)
8. Recommended weighting: Bull __% / Bear __% (based on argument quality)"""

        resp = await self.llm.complete(TaskType.CRITIQUE, system, prompt, 2000, 0.5)
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

        resp = await self.llm.complete(TaskType.SYNTHESIS, system, prompt, 3000, 0.4, "json")
        data = self._extract_json(resp.content)
        return self._calibrate_synthesis(data)

    def _calibrate_synthesis(self, data: dict) -> dict:
        """
        Guardrails & Calibration:
        1. Clamps scores to [0, 100] and confidence to [0.0, 1.0].
        2. Normalizes scenario probabilities so they sum to 1.0.
        3. Enforces anti-contradiction coherence between risk/vitality and final verdict.
        """
        if not isinstance(data, dict) or "error" in data:
            return data

        for score_key in ["vitality_score", "moat_score", "risk_score"]:
            if score_key in data:
                try:
                    data[score_key] = max(0, min(100, int(round(float(data[score_key])))))
                except (ValueError, TypeError):
                    data[score_key] = 50

        if "confidence_score" in data:
            try:
                data["confidence_score"] = max(0.0, min(1.0, float(data["confidence_score"])))
            except (ValueError, TypeError):
                data["confidence_score"] = 0.5

        scenarios = data.get("scenarios")
        if isinstance(scenarios, dict) and all(k in scenarios for k in ("bull", "base", "bear")):
            try:
                p_bull = float(scenarios["bull"].get("probability", 0.33))
                p_base = float(scenarios["base"].get("probability", 0.34))
                p_bear = float(scenarios["bear"].get("probability", 0.33))
                total = p_bull + p_base + p_bear
                if total > 0:
                    scenarios["bull"]["probability"] = round(p_bull / total, 2)
                    scenarios["base"]["probability"] = round(p_base / total, 2)
                    scenarios["bear"]["probability"] = round(
                        1.0 - (scenarios["bull"]["probability"] + scenarios["base"]["probability"]), 2
                    )
            except Exception:
                pass

        risk = data.get("risk_score", 50)
        vitality = data.get("vitality_score", 50)
        verdict = str(data.get("final_verdict", "watch")).lower()

        if risk >= 75 and vitality < 45 and verdict in ("strong_buy", "buy"):
            data["final_verdict"] = "watch"
            data.setdefault("red_flag_matrix", []).append({
                "flag": f"Automated Calibration: Verdict adjusted from '{verdict}' to 'watch' due to high risk ({risk}) and low vitality ({vitality})",
                "severity": "high",
                "category": "operational"
            })

        return data

    def _build_context(self, results: list[dict]) -> str:
        parts = []
        for r in results:
            if r.get("status") == "completed":
                agent_type = r.get("agent_type", "unknown")
                confidence = r.get("confidence", 0.0)
                evidence = r.get("evidence", [])
                latency = r.get("latency_ms", 0)
                data = r.get("data", {})
                evidence_str = "\n".join(f"  - {e[:300]}" for e in evidence[:5]) if evidence else "  (none)"
                parts.append(
                    f"=== {agent_type.upper()} === (confidence: {confidence:.2f}, latency: {latency}ms)\n"
                    f"Evidence:\n{evidence_str}\n\n"
                    f"Data:\n{json.dumps(data, indent=2)[:2000]}"
                )
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
