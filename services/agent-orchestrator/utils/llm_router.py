"""
AEGIS LLM Router — Groq Multi-Model Routing
Routes requests to Groq API (free tier, LPU-accelerated, OpenAI-compatible).
Groq free tier: 14,400 req/day, 30 RPM — zero cost, zero DNS issues on Render.
"""
from __future__ import annotations

import asyncio
import os
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import httpx
import structlog

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Groq API settings
# ---------------------------------------------------------------------------
GROQ_API_URL  = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL    = "llama-3.1-8b-instant"   # Free, very fast, 128k context
# Optional OpenAI fallback (used when GROQ_API_KEY is not set)
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

# Jina AI free embedding endpoint (no key needed for small volumes)
JINA_EMBED_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL     = "jina-embeddings-v2-base-en"


class TaskType(str, Enum):
    SCRAPE_ANALYSIS = "scrape_analysis"
    FINANCIAL       = "financial"
    DEBATE          = "debate"
    SYNTHESIS       = "synthesis"
    CRITIQUE        = "critique"
    CLASSIFICATION  = "classification"
    REPORT          = "report"
    EMBEDDING       = "embedding"


@dataclass
class ModelResponse:
    content:       str
    model:         str
    input_tokens:  int   = 0
    output_tokens: int   = 0
    latency_ms:    int   = 0
    cost_usd:      float = 0.0  # Always 0 — Groq free tier


class LLMRouter:
    def __init__(self):
        self.models:         dict[str, Any]  = {}
        self.tokenizers:     dict[str, Any]  = {}
        self.pipelines:      dict[str, Any]  = {}
        self.embedding_model: Optional[Any]  = None
        self.health:         dict[str, dict] = {}
        self._semaphore = asyncio.Semaphore(3)

    # ------------------------------------------------------------------
    # Public: complete()
    # ------------------------------------------------------------------
    async def complete(
        self,
        task_type: TaskType,
        system: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        response_format: Optional[str] = None,
    ) -> ModelResponse:
        try:
            start = time.monotonic()
            response = await self._call(system, prompt, max_tokens, temperature, response_format)
            latency = int((time.monotonic() - start) * 1000)

            model_key = response.model
            h = self._health(model_key)
            h["avg_latency"] = h["avg_latency"] * 0.9 + latency * 0.1
            h["error_count"] = max(0, h["error_count"] - 1)

            log.info("llm_call_success", model=model_key,
                     tokens=response.input_tokens + response.output_tokens,
                     latency_ms=latency)
            return response

        except Exception as exc:
            # Determine which provider/model to attribute the error to
            model_key = GROQ_MODEL if os.getenv("GROQ_API_KEY", "") else OPENAI_MODEL
            h = self._health(model_key)
            h["error_count"] += 1
            h["last_error"] = time.time()
            if h["error_count"] > 5:
                h["is_available"] = False
            log.error("llm_call_failed", model=model_key, error=str(exc))
            raise

    # ------------------------------------------------------------------
    # Internal: _call()  — Groq chat-completions endpoint
    # ------------------------------------------------------------------
    async def _call(
        self,
        system: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        response_format: Optional[str],
    ) -> ModelResponse:
        start = time.monotonic()

        # Append format hint to the user message
        if response_format == "json":
            prompt += "\n\nRespond with valid JSON only. No markdown fences."
        elif response_format == "toon":
            prompt += "\n\nRespond with valid TOON (Token-Oriented Object Notation) only."

        groq_key = os.getenv("GROQ_API_KEY", "")
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        openai_key = os.getenv("OPENAI_API_KEY", "")

        # Build providers list in preferred order
        providers: list[dict[str, Any]] = []
        if groq_key:
            providers.append({"name": "groq", "url": GROQ_API_URL, "key": groq_key, "model": GROQ_MODEL})
        if openrouter_key:
            providers.append({"name": "openrouter", "url": "https://api.openrouter.ai/v1/chat/completions", "key": openrouter_key, "model": os.getenv("OPENROUTER_MODEL", OPENAI_MODEL)})
        if openai_key:
            providers.append({"name": "openai", "url": OPENAI_API_URL, "key": openai_key, "model": OPENAI_MODEL})

        if not providers:
            raise RuntimeError("No LLM provider configured: set GROQ_API_KEY, OPENROUTER_API_KEY or OPENAI_API_KEY in the environment")

        content = ""
        # Try providers sequentially; each provider gets a small retry loop before moving to next
        async with self._semaphore:
            async with httpx.AsyncClient(timeout=90.0) as client:
                for prov in providers:
                    provider = prov["name"]
                    url = prov["url"]
                    api_key = prov["key"]
                    model_for_provider = prov["model"]

                    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

                    payload: dict[str, Any] = {
                        "model":       model_for_provider,
                        "messages":    [
                            {"role": "system", "content": system},
                            {"role": "user",   "content": prompt},
                        ],
                        "max_tokens":  max_tokens,
                        "temperature": temperature,
                    }

                    # Groq supports native JSON mode via response_format
                    if provider == "groq" and response_format == "json":
                        payload["response_format"] = {"type": "json_object"}

                    # Per-provider attempt loop
                    for attempt in range(3):
                        try:
                            resp = await client.post(url, headers=headers, json=payload)

                            if resp.status_code == 200:
                                data = resp.json()
                                content = data["choices"][0]["message"]["content"]
                                usage = data.get("usage", {})
                                latency = int((time.monotonic() - start) * 1000)
                                return ModelResponse(
                                    content=content,
                                    model=model_for_provider,
                                    input_tokens=usage.get("prompt_tokens", len(system + prompt) // 4),
                                    output_tokens=usage.get("completion_tokens", len(content) // 4),
                                    latency_ms=latency,
                                    cost_usd=0.0,
                                )

                            elif resp.status_code == 429:
                                retry_after = float(resp.headers.get("retry-after", "5")) + random.uniform(0.5, 2.0)
                                log.warning("llm_rate_limited", provider=provider, retry_after=retry_after)
                                await asyncio.sleep(retry_after)
                                continue

                            else:
                                # For non-200/429 status, try again a couple times then move to next provider
                                log.warning("llm_unexpected_status", provider=provider, status=resp.status_code)
                                resp.raise_for_status()

                        except httpx.ConnectError as e:
                            log.error("llm_connect_error", provider=provider, attempt=attempt, error=str(e))
                            # short backoff before retrying same provider
                            await asyncio.sleep(1.0 + random.uniform(0.2, 1.0))
                            continue

                        except Exception as e:
                            log.error("llm_provider_error", provider=provider, attempt=attempt, error=str(e))
                            # try the same provider a couple times; if still failing we'll move to next provider
                            await asyncio.sleep(1.0 + random.uniform(0.2, 1.0))
                            continue

                    # If we reach here, this provider exhausted attempts — move to next provider
                    log.warning("llm_provider_unavailable", provider=provider)

        # All providers exhausted
        raise RuntimeError("All configured LLM providers failed after retries")

    # ------------------------------------------------------------------
    # Public: embed()  — Jina AI free embeddings
    # ------------------------------------------------------------------
    async def embed(self, text: str) -> list[float]:
        """Generate embeddings via Jina AI free API (no key needed for low volume)."""
        jina_key = os.getenv("JINA_API_KEY", "")
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if jina_key:
            headers["Authorization"] = f"Bearer {jina_key}"

        payload = {
            "model": JINA_MODEL,
            "input": [text[:8000]],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(3):
                try:
                    resp = await client.post(JINA_EMBED_URL, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["data"][0]["embedding"]
                    resp.raise_for_status()
                except Exception as e:
                    if attempt == 2:
                        # Graceful degradation: return zero vector so the app doesn't crash
                        log.warning("embed_failed_returning_zeros", error=str(e))
                        return [0.0] * 768
                    await asyncio.sleep(1.5)

        return [0.0] * 768  # fallback

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _health(self, model: str) -> dict:
        if model not in self.health:
            self.health[model] = {
                "error_count":  0,
                "last_error":   0.0,
                "avg_latency":  0.0,
                "is_available": True,
            }
        return self.health[model]

    def get_provider(self, name: str) -> str:
        return name
