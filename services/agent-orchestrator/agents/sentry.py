"""
Sentry Agent — URL monitoring, content extraction, tech stack detection.
The first agent to touch the target URL.
"""
from __future__ import annotations
import re
from agents.base_agent import BaseAgent, AgentResult
from utils.llm_router import TaskType


class SentryAgent(BaseAgent):
    name      = "sentry"
    task_type = TaskType.SCRAPE_ANALYSIS

    SYSTEM = """You are AEGIS Sentry Agent — an expert at extracting structured intelligence
from company websites. Extract ALL signals with high precision. Return ONLY valid JSON."""

    async def _run(self, investigation_id: str, url: str) -> AgentResult:
        # Scrape the target
        await self._emit_event(investigation_id, "in_progress", "Scraping target URL...")
        content = await self.scraper.scrape(url, investigation_id)

        if not content:
            return AgentResult(agent_type=self.name, status="failed",
                               error="Could not scrape URL — blocked or unreachable")

        text = content.get("text", "")
        html = content.get("html", "")
        title = content.get("title", "")

        # Tech stack from HTML signals
        tech_signals = self._detect_tech_stack(html)

        await self._emit_event(investigation_id, "in_progress", "Running LLM analysis...")

        few_shot = await self._few_shot_prompt("sentry_analysis", text[:1000])
        prompt = f"""Analyse this company website and extract structured intelligence.

URL: {url}
Page Title: {title}
Content (first 8000 chars):
{text[:8000]}

Detected Technologies: {tech_signals}
{few_shot}

Return a JSON object with these exact keys:
{{
  "company_name": "...",
  "tagline": "...",
  "description": "...",
  "business_model": "B2B|B2C|B2B2C|marketplace|SaaS|...",
  "industry": "...",
  "founding_stage": "early|growth|late|public",
  "target_customers": ["..."],
  "key_products": ["..."],
  "pricing_model": "subscription|usage|freemium|enterprise|unknown",
  "has_pricing_page": true|false,
  "geographic_presence": ["..."],
  "contact_info": {{"email": "...", "phone": "..."}},
  "social_links": {{"linkedin": "...", "twitter": "...", "github": "..."}},
  "tech_stack": {tech_signals},
  "ui_maturity": "basic|professional|enterprise",
  "content_quality": "thin|moderate|rich",
  "seo_signals": {{"has_blog": true|false, "has_case_studies": true|false}},
  "trust_signals": ["certifications", "awards", "press mentions"],
  "red_flags": ["any concerning signals found"],
  "confidence_notes": "why you are confident or uncertain"
}}"""

        resp = await self.llm.complete(
            task_type=self.task_type,
            system=self.SYSTEM,
            prompt=prompt,
            max_tokens=1500,
            temperature=0.3,
            response_format="json",
        )

        data = self._extract_json(resp.content)
        evidence = [url, f"Scraped {len(text)} chars", f"Tech: {tech_signals}"]

        return AgentResult(
            agent_type=self.name,
            status="completed",
            data={**data, "raw_url": url, "page_title": title},
            confidence=self._confidence_from_evidence(evidence),
            evidence=evidence,
            tokens_used=resp.input_tokens + resp.output_tokens,
        )

    def _detect_tech_stack(self, html: str) -> dict:
        tech: dict[str, list[str]] = {"frontend": [], "analytics": [], "hosting": [], "payments": []}
        patterns = {
            "frontend":  [("React",    r'react'), ("Vue",      r'vue\.js'), ("Next.js",  r'next/'),
                          ("Angular",  r'angular'), ("Tailwind", r'tailwind')],
            "analytics": [("GA4",      r'gtag\('), ("Segment",  r'analytics\.js'), ("Mixpanel", r'mixpanel'),
                          ("Hotjar",   r'hotjar'), ("Amplitude",r'amplitude')],
            "hosting":   [("Vercel",   r'vercel'), ("Netlify",  r'netlify'), ("AWS",      r'amazonaws'),
                          ("Cloudflare", r'cloudflare')],
            "payments":  [("Stripe",   r'stripe'), ("Razorpay", r'razorpay'), ("PayPal",  r'paypal')],
        }
        for category, checks in patterns.items():
            for name, pattern in checks:
                if re.search(pattern, html, re.IGNORECASE):
                    tech[category].append(name)
        return tech
