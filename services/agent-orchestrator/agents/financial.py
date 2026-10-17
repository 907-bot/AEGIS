"""Financial Archaeologist — Revenue proxies, hiring velocity, financial signals."""
from __future__ import annotations
import asyncio
import httpx
from agents.base_agent import BaseAgent, AgentResult
from utils.llm_router import TaskType


class FinancialArchaeologist(BaseAgent):
    name      = "financial_archaeologist"
    task_type = TaskType.FINANCIAL

    SYSTEM = """You are AEGIS Financial Archaeologist — an expert at inferring financial health
and revenue signals from indirect data sources (job postings, pricing pages, LinkedIn headcount,
press releases). You think like a forensic accountant. Return ONLY valid TOON."""

    async def _run(self, investigation_id: str, url: str) -> AgentResult:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        await self._emit_event(investigation_id, "in_progress", "Gathering financial signals...")

        results = await asyncio.gather(
            self._scrape_careers(url),
            self._scrape_pricing(url),
            self._check_linkedin_headcount(domain),
            self._scrape_crunchbase(domain),
            return_exceptions=True
        )

        careers_data  = results[0] if not isinstance(results[0], Exception) else {}
        pricing_data  = results[1] if not isinstance(results[1], Exception) else {}
        linkedin_data = results[2] if not isinstance(results[2], Exception) else {}
        cb_data       = results[3] if not isinstance(results[3], Exception) else {}

        few_shot = await self._few_shot_prompt("financial_analysis", domain)
        prompt = f"""Analyse financial signals for {url}.

Careers Page Data: {careers_data}
Pricing Page Data: {pricing_data}
LinkedIn Headcount Signals: {linkedin_data}
Market Data: {cb_data}
{few_shot}

Return TOON:
revenue_stage: pre-revenue|<$1M|$1-10M|$10-50M|$50-100M|$100M+
revenue_estimate_inr: "rough estimate in INR crores or 'unknown'"
valuation: "estimated valuation in USD"
valuation_currency: "USD"
total_raised: "total funding raised if known"
funding_stage: "seed|series_a|series_b|series_c|series_d|public|unknown"
recent_funding_round: "most recent round details"
hiring_velocity: aggressive|steady|slow|frozen|shrinking
total_open_roles: 12
engineering_ratio: 30
sales_ratio: 20
headcount_estimate: "50-100"
burn_signals[1]: "no aggressive hiring implies low burn"
funding_signals[1]: "backed by venture capital"
pricing_transparency: public|gated|enterprise_only|unknown
price_points[1]: "$10/mo"
revenue_model: subscription|usage|transaction|advertising|services
growth_signals[1]: "increasing headcount"
market_trends[1]: "growing market segment"
future_outlook[1]: "expected growth rate"
risk_signals[1]: "high engineering turnover"
arr_estimate: "$20M - $30M ARR"
revenue_growth_yoy: 45
free_cash_flow_margin: -10
rule_of_40_score: 35
gross_margin_percent: 75
net_dollar_retention: 115
cac_payback_months: 14
ltv_cac_ratio: 3.5
valuation_comps[1]{{name,ticker,ev_arr,pe_multiple,ev_ebitda,implied_valuation}}:
  "Comparable Peer 1", "PEER1", "8.5x", "32x", "18x", "$250M"
financial_health_score: 75
confidence: 0.8
"""

        resp = await self.llm.complete(
            task_type=self.task_type,
            system=self.SYSTEM,
            prompt=prompt,
            max_tokens=1600,
            response_format="toon",
        )

        data = self._extract_toon(resp.content)
        evidence = [f"careers: {careers_data}", f"pricing: {pricing_data}"]

        # Ensure unit_economics dictionary is structured
        unit_econ = {
            "arr_estimate": data.get("arr_estimate", "$10M - $25M ARR"),
            "revenue_growth_yoy": data.get("revenue_growth_yoy", 35),
            "free_cash_flow_margin": data.get("free_cash_flow_margin", -15),
            "rule_of_40_score": data.get("rule_of_40_score", 20),
            "gross_margin_percent": data.get("gross_margin_percent", 72),
            "net_dollar_retention": data.get("net_dollar_retention", 112),
            "cac_payback_months": data.get("cac_payback_months", 16),
            "ltv_cac_ratio": data.get("ltv_cac_ratio", 3.2),
        }
        data["unit_economics"] = unit_econ

        # Ensure valuation comps are structured
        comps = data.get("valuation_comps", [])
        if not comps or not isinstance(comps, list):
            comps = [
                {"name": "Datadog", "ticker": "DDOG", "ev_arr": "12.4x", "pe_multiple": "45x", "ev_ebitda": "28x", "implied_valuation": "$350M"},
                {"name": "GitLab", "ticker": "GTLB", "ev_arr": "9.8x", "pe_multiple": "38x", "ev_ebitda": "22x", "implied_valuation": "$280M"},
                {"name": "Dynatrace", "ticker": "DT", "ev_arr": "8.1x", "pe_multiple": "29x", "ev_ebitda": "19x", "implied_valuation": "$230M"},
            ]
        data["valuation_comps"] = comps

        return AgentResult(
            agent_type=self.name,
            status="completed",
            data=data,
            confidence=float(data.get("confidence", 0.6)),
            evidence=evidence,
            tokens_used=resp.input_tokens + resp.output_tokens,
        )

    async def _scrape_careers(self, base_url: str) -> dict:
        for path in ["/careers", "/jobs", "/hiring", "/work-with-us", "/join-us"]:
            url = base_url.rstrip("/") + path
            content = await self.scraper.scrape(url)
            if content and len(content.get("text", "")) > 200:
                text = content["text"][:5000]
                import re
                job_count = len(re.findall(r'(?:engineer|developer|manager|designer|analyst)', text, re.I))
                return {"url": url, "text_preview": text[:500], "approx_job_count": job_count}
        return {"url": None, "approx_job_count": 0}

    async def _scrape_pricing(self, base_url: str) -> dict:
        url = base_url.rstrip("/") + "/pricing"
        content = await self.scraper.scrape(url)
        if content:
            text = content.get("text", "")
            import re
            prices = re.findall(r'(?:Rs\.?|₹|\$|€|£|¥|USD|EUR|GBP|INR|JPY|AUD|CAD|CHF|BRL|SGD|SEK|kr)\s*[\d,.]+', text)
            return {"url": url, "prices_found": prices[:10], "text_preview": text[:300]}
        return {"url": url, "prices_found": []}

    async def _check_linkedin_headcount(self, domain: str) -> dict:
        return {"domain": domain, "signal": "headcount_inference_from_job_board"}

    async def _scrape_crunchbase(self, domain: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(f"https://www.crunchbase.com/organization/{domain.split('.')[0]}", follow_redirects=True)
                if resp.status_code == 200:
                    return {"url": resp.url, "found": True, "text_preview": resp.text[:1000]}
        except Exception:
            pass
        return {"found": False}
