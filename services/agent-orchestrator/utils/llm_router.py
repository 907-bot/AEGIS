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
            start    = time.monotonic()
            response = await self._call(system, prompt, max_tokens, temperature, response_format)
            latency  = int((time.monotonic() - start) * 1000)

            h = self._health(GROQ_MODEL)
            h["avg_latency"] = h["avg_latency"] * 0.9 + latency * 0.1
            h["error_count"] = max(0, h["error_count"] - 1)

            log.info("llm_call_success", model=GROQ_MODEL,
                     tokens=response.input_tokens + response.output_tokens,
                     latency_ms=latency)
            return response

        except Exception as exc:
            h = self._health(GROQ_MODEL)
            h["error_count"] += 1
            h["last_error"]   = time.time()
            if h["error_count"] > 5:
                h["is_available"] = False
            log.error("llm_call_failed", model=GROQ_MODEL, error=str(exc))
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

        api_key = os.getenv("GROQ_API_KEY", "")
        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        payload: dict[str, Any] = {
            "model":       GROQ_MODEL,
            "messages":    [
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens":  max_tokens,
            "temperature": temperature,
        }

        # Groq supports native JSON mode
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        content = ""
        async with self._semaphore:
            async with httpx.AsyncClient(timeout=90.0) as client:
                for attempt in range(4):
                    try:
                        resp = await client.post(GROQ_API_URL, headers=headers, json=payload)

                        if resp.status_code == 200:
                            data    = resp.json()
                            content = data["choices"][0]["message"]["content"]
                            usage   = data.get("usage", {})
                            latency = int((time.monotonic() - start) * 1000)
                            return ModelResponse(
                                content=content,
                                model=GROQ_MODEL,
                                input_tokens=usage.get("prompt_tokens", len(system + prompt) // 4),
                                output_tokens=usage.get("completion_tokens", len(content) // 4),
                                latency_ms=latency,
                                cost_usd=0.0,
                            )

                        elif resp.status_code == 429:
                            # Rate-limited — back off with jitter and retry
                            retry_after = float(resp.headers.get("retry-after", "5")) + random.uniform(0.5, 2.0)
                            log.warning("groq_rate_limited", retry_after=retry_after)
                            await asyncio.sleep(retry_after)

                        else:
                            resp.raise_for_status()

                    except httpx.ConnectError as e:
                        log.error("groq_connect_error", attempt=attempt, error=str(e))
                        if attempt == 3:
                            raise
                        await asyncio.sleep(3.0 * (attempt + 1) + random.uniform(0.5, 2.0))

                    except Exception as e:
                        if attempt == 3:
                            raise
                        await asyncio.sleep(2.0 + random.uniform(0.5, 2.0))

        raise RuntimeError("Groq API call failed after all retries")

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