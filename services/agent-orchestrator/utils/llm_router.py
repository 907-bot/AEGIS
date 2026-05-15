"""
AEGIS LLM Router — Intelligent Multi-Provider Routing
Routes requests to OpenAI / Anthropic / local based on task type,
cost budget, latency requirements, and provider health.
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import structlog
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
import google.generativeai as genai

log = structlog.get_logger()


class Provider(str, Enum):
    OPENAI    = "openai"
    ANTHROPIC = "anthropic"
    GEMINI    = "gemini"
    FALLBACK  = "fallback"


class TaskType(str, Enum):
    SCRAPE_ANALYSIS  = "scrape_analysis"
    FINANCIAL        = "financial"
    DEBATE           = "debate"
    SYNTHESIS        = "synthesis"
    CRITIQUE         = "critique"
    CLASSIFICATION   = "classification"
    REPORT           = "report"
    EMBEDDING        = "embedding"


@dataclass
class ProviderHealth:
    error_count:   int   = 0
    last_error:    float = 0.0
    avg_latency:   float = 0.0
    is_available:  bool  = True


@dataclass
class LLMResponse:
    content:       str
    provider:      Provider
    model:         str
    input_tokens:  int = 0
    output_tokens: int = 0
    latency_ms:    int = 0
    cost_usd:      float = 0.0


# Cost per 1K tokens (input / output)
COST_TABLE = {
    "gpt-4o":                   (0.005, 0.015),
    "gpt-4o-mini":              (0.00015, 0.0006),
    "claude-3-5-sonnet-20241022": (0.003, 0.015),
    "claude-3-haiku-20240307":  (0.00025, 0.00125),
    "gemini-2.0-flash":         (0.000075, 0.0003),
    "gemini-1.5-pro":           (0.0035, 0.0105),
}

# Which model to use per task
# Primary: OpenAI (gpt-4o-mini) — cheapest capable LLM
# Gemini and Anthropic used as fallbacks only
TASK_ROUTING: dict[TaskType, tuple[Provider, str]] = {
    TaskType.SCRAPE_ANALYSIS: (Provider.OPENAI,    "gpt-4o-mini"),
    TaskType.FINANCIAL:       (Provider.OPENAI,    "gpt-4o-mini"),
    TaskType.DEBATE:          (Provider.OPENAI,    "gpt-4o-mini"),
    TaskType.SYNTHESIS:       (Provider.OPENAI,    "gpt-4o-mini"),
    TaskType.CRITIQUE:        (Provider.OPENAI,    "gpt-4o-mini"),
    TaskType.CLASSIFICATION:  (Provider.OPENAI,    "gpt-4o-mini"),
    TaskType.REPORT:          (Provider.OPENAI,    "gpt-4o-mini"),
    TaskType.EMBEDDING:       (Provider.OPENAI,    "text-embedding-3-small"),
}

FALLBACK_ROUTING: dict[Provider, tuple[Provider, str]] = {
    Provider.OPENAI:    (Provider.ANTHROPIC, "claude-3-haiku-20240307"),
    Provider.ANTHROPIC: (Provider.GEMINI, "gemini-2.0-flash"),
    Provider.GEMINI:    (Provider.OPENAI, "gpt-4o-mini"),
}


class LLMRouter:
    def __init__(self):
        self.openai    = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "sk-placeholder"))
        self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", "sk-ant-placeholder"))
        genai.configure(api_key=os.getenv("GEMINI_API_KEY", "AIza-placeholder"))
        self.gemini = genai
        
        self.health: dict[Provider, ProviderHealth] = {
            Provider.OPENAI:    ProviderHealth(),
            Provider.ANTHROPIC: ProviderHealth(),
            Provider.GEMINI:    ProviderHealth(),
        }

    async def complete(
        self,
        task_type: TaskType,
        system: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        provider, model = TASK_ROUTING[task_type]

        # Health check — fall back if too many errors
        if not self.health[provider].is_available:
            fb_provider, fb_model = FALLBACK_ROUTING[provider]
            log.warning("provider_unhealthy_fallback", from_=provider, to=fb_provider)
            provider, model = fb_provider, fb_model

        try:
            start = time.monotonic()
            response = await self._call(provider, model, system, prompt, max_tokens,
                                        temperature, response_format)
            latency = int((time.monotonic() - start) * 1000)

            # Update health
            h = self.health[provider]
            h.avg_latency = (h.avg_latency * 0.9) + (latency * 0.1)
            h.error_count  = max(0, h.error_count - 1)

            log.info("llm_call_success", provider=provider, model=model,
                     tokens=response.input_tokens + response.output_tokens, latency_ms=latency)
            return response

        except Exception as exc:
            h = self.health[provider]
            h.error_count += 1
            h.last_error   = time.time()
            if h.error_count > 5:
                h.is_available = False
                asyncio.create_task(self._restore_provider(provider))

            log.error("llm_call_failed", provider=provider, error=str(exc))

            # Cascade through fallbacks until one works
            attempted = {provider}
            fb_provider, fb_model = FALLBACK_ROUTING.get(provider, (Provider.OPENAI, "gpt-4o-mini"))
            while fb_provider not in attempted:
                attempted.add(fb_provider)
                try:
                    log.warning("llm_fallback", from_=provider, to=fb_provider, model=fb_model)
                    return await self._call(fb_provider, fb_model, system, prompt,
                                            max_tokens, temperature, response_format)
                except Exception as fb_exc:
                    log.error("llm_fallback_failed", provider=fb_provider, error=str(fb_exc))
                    fb_provider, fb_model = FALLBACK_ROUTING.get(fb_provider, (Provider.OPENAI, "gpt-4o-mini"))
            raise

    async def _call(
        self, provider: Provider, model: str, system: str, prompt: str,
        max_tokens: int, temperature: float, response_format: Optional[str],
    ) -> LLMResponse:
        start = time.monotonic()

        if provider == Provider.OPENAI:
            kwargs: dict[str, Any] = {}
            if response_format == "json":
                kwargs["response_format"] = {"type": "json_object"}
            resp = await self.openai.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=60.0,
                **kwargs,
            )
            content = resp.choices[0].message.content or ""
            in_tok  = resp.usage.prompt_tokens
            out_tok = resp.usage.completion_tokens

        elif provider == Provider.ANTHROPIC:
            resp = await self.anthropic.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                timeout=60.0,
            )
            content = resp.content[0].text if resp.content else ""
            in_tok  = resp.usage.input_tokens
            out_tok = resp.usage.output_tokens

        else:  # GEMINI
            m = self.gemini.GenerativeModel(model)
            resp = await m.generate_content_async(
                contents=[{"role": "user", "parts": [f"System: {system}\n\nUser: {prompt}"]}],
                generation_config=self.gemini.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                ),
                request_options={"timeout": 60.0}
            )
            content = resp.text
            in_tok  = max(1, len(prompt) // 4)
            out_tok = max(1, len(content) // 4)

        latency   = int((time.monotonic() - start) * 1000)
        in_cost, out_cost = COST_TABLE.get(model, (0.005, 0.015))
        cost_usd  = (in_tok / 1000) * in_cost + (out_tok / 1000) * out_cost

        return LLMResponse(
            content=content, provider=provider, model=model,
            input_tokens=in_tok, output_tokens=out_tok,
            latency_ms=latency, cost_usd=cost_usd,
        )

    async def embed(self, text: str) -> list[float]:
        resp = await self.openai.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000],
        )
        return resp.data[0].embedding

    async def _restore_provider(self, provider: Provider, delay: int = 60):
        await asyncio.sleep(delay)
        self.health[provider].is_available = True
        self.health[provider].error_count  = 0
        log.info("provider_restored", provider=provider)

    def get_provider(self, name: str):
        """For CrewAI compatibility — returns provider name string."""
        return name
