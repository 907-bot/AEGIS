"""Investigation Workflow — Final report generation."""
from __future__ import annotations
import json
import re
from urllib.parse import urlparse
from utils.llm_router import LLMRouter, TaskType


class InvestigationWorkflow:
    def __init__(self, llm_router: LLMRouter):
        self.llm = llm_router

    async def generate_report(
        self, investigation_id: str, url: str, debate: dict, recon: list[dict]
    ) -> dict:
        system = """You are AEGIS Chief Report Officer. Generate a comprehensive strategic intelligence
report from multi-agent analysis. Be precise, evidence-based, and actionable. Return ONLY valid JSON."""

        context = json.dumps({
            "debate_synthesis": {k: v for k, v in debate.items()
                                 if k not in ["bull_thesis", "bear_thesis"]},
            "recon_summary": [
                {"agent": r.get("agent_type"), "key_findings": str(r.get("data", {}))[:500]}
                for r in recon if r.get("status") == "completed"
            ][:7],
        })

        prompt = f"""Generate a complete AEGIS strategic intelligence report.
Investigation ID: {investigation_id}
Target URL: {url}
URL-derived company name: {self._company_from_url(url)}

Analysis Context:
{context[:6000]}

Return JSON (all fields required). IMPORTANT: Every field must have REAL, SUBSTANTIVE content. Do NOT use placeholder text like "..." or "full markdown report". The raw_markdown field must be a COMPLETE multi-section markdown report with real data.

SCHEMA:
{{
  "company_name": "real company name derived from the analysis",
  "confidence_score": 0.0-1.0,
  "vitality_score": 0-100,
  "moat_score": 0-100,
  "risk_score": 0-100,
  "executive_summary": "comprehensive summary (4-5 sentences with real insights)",
  "bull_thesis": "detailed bull case argument with evidence",
  "bear_thesis": "detailed bear case argument with evidence",
  "skeptic_analysis": "critical audit of assumptions and risks",
  "final_verdict": "strong_buy|buy|hold|watch|avoid",
  "industry": "technology|finance|healthcare|etc",
  "business_model": "SaaS|marketplace|subscription|etc",
  "headcount_estimate": "50-100",
  "geographic_presence": ["US", "India"],
  "founding_stage": "early|growth|late|public",
  "funding_stage": "seed|series_a|series_b|series_c|public",
  "total_raised": "$10M",
  "valuation": "$50M",
  "revenue_stage": "$10-50M",
  "revenue_estimate_inr": "₹100Cr",
  "revenue_model": "subscription|usage|etc",
  "pricing_model": "freemium|enterprise|etc",
  "financial_health_score": 75,
  "hiring_velocity": "aggressive|steady|slow",
  "total_open_roles": 30,
  "market_position": "leader|challenger|niche",
  "market_size_estimate": "large|medium|niche",
  "market_maturity": "growing|mature|emerging",
  "momentum": "accelerating|steady",
  "overall_sentiment": "positive|neutral|negative",
  "sentiment_score": 70,
  "brand_perception": "premium|mainstream|technical",
  "team_quality_score": 75,
  "compliance_score": 80,
  "logo_url": "https://company.com/logo.png",
  "ceo": {{
    "name": "CEO Name",
    "background": "Previous companies and education",
    "photo_url": "https://..."
  }},
  "co_founders": [
    {{"name": "Co-Founder Name", "role": "CTO", "background": "ex-Google, Stanford", "photo_url": "https://..."}}
  ],
  "leadership_team": [
    {{"name": "Exec Name", "role": "VP Engineering", "background": "15 yrs at Microsoft", "photo_url": "https://..."}}
  ],
  "founder_background": ["ex-FAANG", "Stanford"],
  "office_locations": ["HQ: San Francisco"],
  "branch_offices": ["London", "Bangalore"],
  "red_flag_matrix": [
    {{"flag": "specific risk", "severity": "low|medium|high|critical", "category": "risk category"}}
  ],
  "moat_analysis": {{
    "primary_moat": "competitive advantage type", "strength": "wide|narrow|none", "durability_years": 5
  }},
  "scenarios": {{
    "bull": {{"probability": 0.3, "outcome": "best case", "price_target": "market estimate"}},
    "base": {{"probability": 0.5, "outcome": "most likely", "price_target": "market estimate"}},
    "bear": {{"probability": 0.2, "outcome": "worst case", "price_target": "market estimate"}}
  }},
  "recommendations": [
    {{"action": "specific action", "rationale": "why this matters", "priority": "immediate|short_term|long_term"}}
  ],
  "comparable_companies": ["Real competitor name"],
  "next_monitoring_triggers": ["specific event to watch"],
  "raw_markdown": "# AEGIS Report\n\n## Executive Summary\n...\n\n## Company Overview\n...\n\n## Leadership\n...\n\n## Financial Analysis\n...\n\n## Market Position\n...\n\n## Bull Case\n...\n\n## Bear Case\n...\n\n## Risk Matrix\n...\n\n## Scenario Analysis\n...\n\n## Recommendations\n..."
}}"""

        resp = await self.llm.complete(TaskType.REPORT, system, prompt, 3000, 0.4, "json")

        import re
        text = resp.content
        try:
            data = json.loads(text)
        except Exception:
            match = re.search(r'\{[\s\S]*\}', text)
            data = json.loads(match.group()) if match else {}

        # Merge debate synthesis fields if missing
        for key in ["company_name", "confidence_score", "vitality_score", "moat_score", "risk_score"]:
            if key not in data and key in debate:
                data[key] = debate[key]

        # Generate markdown if missing or placeholder
        md = data.get("raw_markdown", "")
        if not md or "full markdown" in md.lower() or len(md) < 200:
            data["raw_markdown"] = self._to_markdown(data, url)

        return data

    def _to_markdown(self, report: dict, url: str) -> str:
        rm = report.get('red_flag_matrix', [])
        recs = report.get('recommendations', [])
        comparable = report.get('comparable_companies', [])
        triggers = report.get('next_monitoring_triggers', [])
        scenarios = report.get('scenarios', {})
        moat = report.get('moat_analysis', {})

        return f"""# AEGIS Strategic Intelligence Report

**Target:** {url}
**Company:** {report.get('company_name', 'Unknown')}
**Verdict:** {report.get('final_verdict', 'N/A').upper()}
**Confidence:** {report.get('confidence_score', 'N/A')}
**Generated:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M UTC')}

---

## 1. Executive Summary

{report.get('executive_summary', 'No executive summary available.')}

## 2. Company Overview

- **Company Name:** {report.get('company_name', 'Unknown')}
- **Industry:** {report.get('industry', report.get('industry_category', 'N/A'))}
- **Business Model:** {report.get('business_model', 'N/A')}
- **Stage:** {report.get('founding_stage', 'N/A')}
- **Headcount:** {report.get('headcount_estimate', 'N/A')}
- **Geographic Presence:** {', '.join(report.get('geographic_presence', [])) if isinstance(report.get('geographic_presence'), list) else report.get('geographic_presence', 'N/A')}
- **Funding Stage:** {report.get('funding_stage', 'N/A')}
- **Total Raised:** {report.get('total_raised', 'N/A')}
- **Valuation:** {report.get('valuation', 'N/A')}

## 3. Leadership & Team

**CEO:** {report.get('ceo', {}).get('name', 'N/A')}
**CEO Background:** {report.get('ceo', {}).get('background', 'N/A')}

**Co-Founders:**
{chr(10).join(f"- {cf.get('name', 'Unknown')} ({cf.get('role', 'Co-Founder')}) — {cf.get('background', '')}" for cf in (report.get('co_founders', []) if isinstance(report.get('co_founders'), list) else [])) or "No co-founder data available."}

**Executive Team:**
{chr(10).join(f"- {l.get('name', 'Unknown')} — {l.get('role', '')}" for l in (report.get('leadership_team', []) if isinstance(report.get('leadership_team'), list) else [])) or "No executive team data available."}

**Founder Background Signals:**
{chr(10).join(f"- {fb}" for fb in (report.get('founder_background', []) if isinstance(report.get('founder_background'), list) else [report.get('founder_background', '')] if report.get('founder_background') else [])) or "No founder background data."}

**Team Quality Score:** {report.get('team_quality_score', 'N/A')}/100
**Hiring Velocity:** {report.get('hiring_velocity', 'N/A')}

## 4. Financial Analysis

- **Revenue Stage:** {report.get('revenue_stage', 'N/A')}
- **Revenue Estimate:** {report.get('revenue_estimate_inr', 'N/A')}
- **Valuation Estimate:** {report.get('valuation', 'N/A')}
- **Total Raised:** {report.get('total_raised', 'N/A')}
- **Funding Stage:** {report.get('funding_stage', 'N/A')}
- **Revenue Model:** {report.get('revenue_model', 'N/A')}
- **Pricing Model:** {report.get('pricing_model', report.get('pricing_transparency', 'N/A'))}
- **Price Points:** {', '.join(report.get('price_points', [])) if isinstance(report.get('price_points'), list) else report.get('price_points', 'N/A')}
- **Total Open Roles:** {report.get('total_open_roles', 'N/A')}
- **Financial Health Score:** {report.get('financial_health_score', 'N/A')}/100

**Growth Signals:**
{chr(10).join(f"- {gs}" for gs in (report.get('growth_signals', []) if isinstance(report.get('growth_signals'), list) else [report.get('growth_signals', '')] if report.get('growth_signals') else [])) or "No growth signals detected."}

**Risk Signals:**
{chr(10).join(f"- {rs}" for rs in (report.get('risk_signals', []) if isinstance(report.get('risk_signals'), list) else [report.get('risk_signals', '')] if report.get('risk_signals') else [])) or "No risk signals detected."}

## 5. Market Position & Competitive Landscape

- **Market Position:** {report.get('market_position', 'N/A')}
- **Market Size:** {report.get('market_size_estimate', 'N/A')}
- **Market Maturity:** {report.get('market_maturity', 'N/A')}
- **Market Momentum:** {report.get('momentum', 'N/A')}
- **Brand Perception:** {report.get('brand_perception', 'N/A')}
- **Overall Sentiment:** {report.get('overall_sentiment', 'N/A')}
- **Sentiment Score:** {report.get('sentiment_score', 'N/A')}/100

**Moat Analysis:**
- **Moat Type:** {moat.get('type', moat.get('primary_moat', 'N/A'))}
- **Moat Strength:** {moat.get('strength', 'N/A')}
- **Durability:** {moat.get('durability_years', moat.get('durability', 'N/A'))}

**Direct Competitors:**
{chr(10).join(f"- {c.get('name', c) if isinstance(c, dict) else c} (Similarity: {c.get('similarity', 'N/A') if isinstance(c, dict) else 'N/A'}, Threat: {c.get('threat_level', 'N/A') if isinstance(c, dict) else 'N/A'})" for c in (report.get('direct_competitors', []) if isinstance(report.get('direct_competitors'), list) else [])) or "No competitor data available."}

**Comparable Companies:** {', '.join(comparable) if comparable else 'N/A'}

**Market Trends & Future Outlook:**
{chr(10).join(f"- {mt}" for mt in (report.get('market_trends', []) if isinstance(report.get('market_trends'), list) else [report.get('market_trends', '')] if report.get('market_trends') else [])) or "No market trend data."}
{chr(10).join(f"- {fo}" for fo in (report.get('future_outlook', []) if isinstance(report.get('future_outlook'), list) else [report.get('future_outlook', '')] if report.get('future_outlook') else [])) or "No future outlook data."}

## 6. Bull Case

{report.get('bull_thesis', 'No bull thesis available.')}

## 7. Bear Case

{report.get('bear_thesis', 'No bear thesis available.')}

## 8. Skeptic Audit

{report.get('skeptic_analysis', 'No skeptic analysis available.')}

## 9. Risk Matrix

{chr(10).join(f"- **{r.get('flag', 'Unknown Risk')}** — Severity: {r.get('severity', 'N/A').upper()} — Category: {r.get('category', 'N/A')}" for r in rm) if rm else "No risks identified."}

## 10. Scenario Analysis

**Bull Scenario** (Probability: {scenarios.get('bull', {}).get('probability', 'N/A')}):
{scenarios.get('bull', {}).get('outcome', 'N/A')}
Price Target: {scenarios.get('bull', {}).get('price_target', 'N/A')}

**Base Scenario** (Probability: {scenarios.get('base', {}).get('probability', 'N/A')}):
{scenarios.get('base', {}).get('outcome', 'N/A')}
Price Target: {scenarios.get('base', {}).get('price_target', 'N/A')}

**Bear Scenario** (Probability: {scenarios.get('bear', {}).get('probability', 'N/A')}):
{scenarios.get('bear', {}).get('outcome', 'N/A')}
Price Target: {scenarios.get('bear', {}).get('price_target', 'N/A')}

## 11. Recommendations

{chr(10).join(f"- [{r.get('priority', 'N/A').upper()}] {r.get('action', 'N/A')}: {r.get('rationale', '')}" for r in recs) if recs else "No recommendations available."}

## 12. Monitoring Triggers

{chr(10).join(f"- {t}" for t in triggers) if triggers else "No monitoring triggers defined."}

## 13. Scoring Summary

| Metric | Score (0-100) |
|--------|---------------|
| Vitality | {report.get('vitality_score', 'N/A')} |
| Moat | {report.get('moat_score', 'N/A')} |
| Risk | {report.get('risk_score', 'N/A')} |
| Financial Health | {report.get('financial_health_score', 'N/A')} |
| Team Quality | {report.get('team_quality_score', 'N/A')} |
| Compliance | {report.get('compliance_score', 'N/A')} |
| Confidence | {report.get('confidence_score', 'N/A')} |

---

*Generated by AEGIS v1.0 — Autonomous Multi-Agent Strategic Intelligence Platform*
*Report ID: {report.get('investigation_id', 'N/A')}*
*This report is for informational purposes only and does not constitute financial advice.*
"""

    @staticmethod
    def _company_from_url(url: str) -> str:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        domain = re.sub(r"^www\d?\.", "", domain.split(":")[0])
        parts = domain.split(".")
        if len(parts) >= 2:
            name = parts[-2]
        else:
            name = parts[0]
        name = re.sub(r"[-_]", " ", name)
        return name.title()
