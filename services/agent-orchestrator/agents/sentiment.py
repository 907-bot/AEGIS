"""Sentiment Scout — Market sentiment from public sources."""
from __future__ import annotations
from agents.base_agent import BaseAgent, AgentResult
from utils.llm_router import TaskType


class SentimentScout(BaseAgent):
    name      = "sentiment_scout"
    task_type = TaskType.CLASSIFICATION

    SYSTEM = "You are AEGIS Sentiment Intelligence Agent. Analyse market perception from public signals. Return ONLY valid TOON."

    async def _run(self, investigation_id: str, url: str) -> AgentResult:
        await self._emit_event(investigation_id, "in_progress", "Scanning public sentiment...")
        content = await self.scraper.scrape(url)
        text = content.get("text", "")[:5000] if content else ""

        # Try to scrape press/blog
        blog = await self.scraper.scrape(url.rstrip("/") + "/blog")
        press = await self.scraper.scrape(url.rstrip("/") + "/press")
        extra = ""
        if blog: extra += blog.get("text", "")[:2000]
        if press: extra += press.get("text", "")[:2000]

        prompt = f"""Analyse market sentiment for {url}.
Website Content: {text}
Blog/Press Content: {extra}

Return TOON:
overall_sentiment: very_positive|positive|neutral|negative|very_negative
sentiment_score: 50
brand_perception: premium|mainstream|budget|technical|consumer
customer_love_signals[1]: "testimonials found"
negative_signals[1]: "complaints"
press_coverage: extensive|moderate|minimal|none
social_media_presence: strong|moderate|weak|none
community_signals[1]: "open source"
nps_proxy: likely_high|likely_medium|likely_low|unknown
momentum: accelerating|steady|decelerating|unknown
confidence: 0.8
"""

        resp = await self.llm.complete(self.task_type, self.SYSTEM, prompt, 700, 0.3, "toon")
        data = self._extract_toon(resp.content)
        return AgentResult(agent_type=self.name, status="completed", data=data,
                           confidence=float(data.get("confidence", 0.5)),
                           evidence=[url], tokens_used=resp.input_tokens + resp.output_tokens)
