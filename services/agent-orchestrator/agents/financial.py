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
press releases). You think like a forensic accountant. Return ONLY valid JSON."""

    async def _run(self, investigation_id: str, url: str) -> AgentResult:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        await self._emit_event(investigation_id, "in_progress", "Gathering financial signals...")

        # Gather multiple data sources in parallel
        results = await asyncio.gather(
            self._scrape_careers(url),
            self._scrape_pricing(url),
            self._check_linkedin_headcount(domain),
            return_exceptions=True
        )

        careers_data  = results[0] if not isinstance(results[0], Exception) else {}
        pricing_data  = results[1] if not isinstance(results[1], Exception) else {}
        linkedin_data = results[2] if not isinstance(results[2], Exception) else {}

        few_shot = await self._few_shot_prompt("financial_analysis", domain)
        prompt = f"""Analyse financial signals for {url}.

Careers Page Data: {careers_data}
Pricing Page Data: {pricing_data}
LinkedIn Headcount Signals: {linkedin_data}
{few_shot}

Return JSON:
{{
  "revenue_stage": "pre-revenue|<$1M|$1-10M|$10-50M|$50-100M|$100M+",
  "revenue_estimate_inr": "rough estimate in INR crores or 'unknown'",
  "hiring_velocity": "aggressive|steady|slow|frozen|shrinking",
  "total_open_roles": <number or null>,
  "engineering_ratio": "<percent of eng roles vs total>",
  "sales_ratio": "<percent of sales/gtm roles>",
  "headcount_estimate": "<range or unknown>",
  "burn_signals": ["signals suggesting high/low burn"],
  "funding_signals": ["signals about funding stage"],
  "pricing_transparency": "public|gated|enterprise_only|unknown",
  "price_points": ["any pricing found"],
  "revenue_model": "subscription|usage|transaction|advertising|services",
  "growth_signals": ["positive revenue signals"],
  "risk_signals": ["concerning financial signals"],
  "financial_health_score": <0-100>,
  "confidence": <0.0-1.0>
}}"""

        resp = await self.llm.complete(
            task_type=self.task_type,
            system=self.SYSTEM,
            prompt=prompt,
            max_tokens=1200,
        )

        data = self._extract_json(resp.content)
        evidence = [f"careers: {careers_data}", f"pricing: {pricing_data}"]

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
                # Count job listings
                import re
                job_count = len(re.findall(r'(?:engineer|developer|manager|designer|analyst)',
                                           text, re.I))
                return {"url": url, "text_preview": text[:500], "approx_job_count": job_count}
        return {"url": None, "approx_job_count": 0}

    async def _scrape_pricing(self, base_url: str) -> dict:
        url = base_url.rstrip("/") + "/pricing"
        content = await self.scraper.scrape(url)
        if content:
            text = content.get("text", "")
            import re
            prices = re.findall(r'(?:Rs\.?|₹|\$|USD|INR)\s*[\d,]+', text)
            return {"url": url, "prices_found": prices[:10], "text_preview": text[:300]}
        return {"url": url, "prices_found": []}

    async def _check_linkedin_headcount(self, domain: str) -> dict:
        # Publicly infer from domain — not direct LinkedIn scraping
        return {"domain": domain, "signal": "headcount_inference_from_job_board"}
