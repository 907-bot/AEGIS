"""
AEGIS LLM Router — Multi-Provider Routing with Health Awareness & Retries
Routes requests through Groq → OpenRouter → OpenAI → Ollama with per-provider
timeouts, exponential backoff, and health-aware provider skipping.
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
# Cloud API settings
# ---------------------------------------------------------------------------
GROQ_API_URL  = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL    = "llama-3.1-8b-instant"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Jina AI free embedding endpoint
JINA_EMBED_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL     = "jina-embeddings-v2-base-en"

# ---------------------------------------------------------------------------
# Local LLM settings
# ---------------------------------------------------------------------------
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/v1/chat/completions")
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL", "gemma4:latest")

# Per-provider timeout budgets (seconds)
PROVIDER_TIMEOUTS: dict[str, float] = {
    "groq":      60.0,
    "openrouter": 30.0,
    "openai":    60.0,
    "ollama":   120.0,
}

# How long (seconds) to wait before retrying a provider that was marked unavailable
PROVIDER_COOLDOWN = 60.0

# Max errors before marking provider unavailable
MAX_PROVIDER_ERRORS = 5


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

    # ------------------------------------------------------------------
    # Internal: _call()  — Multi-provider routing with health awareness
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

        if response_format == "json":
            prompt += "\n\nRespond with valid JSON only. No markdown fences."
        elif response_format == "toon":
            prompt += "\n\nRespond with valid TOON (Token-Oriented Object Notation) only."

        providers = self._build_providers()
        if not providers:
            raise RuntimeError(
                "No LLM provider configured: set GROQ_API_KEY, OPENROUTER_API_KEY, "
                "OPENAI_API_KEY or OLLAMA_API_URL in the environment"
            )

        async with self._semaphore:
            for prov in providers:
                provider = prov["name"]

                # Health check: skip providers that have been failing recently
                h = self._health(provider)
                if not h["is_available"]:
                    since_last_error = time.time() - h["last_error"]
                    if since_last_error < PROVIDER_COOLDOWN:
                        log.info("llm_skip_unavailable", provider=provider,
                                 cooldown_remaining=PROVIDER_COOLDOWN - since_last_error)
                        continue
                    else:
                        h["is_available"] = True
                        h["error_count"] = 0
                        log.info("llm_retry_provider", provider=provider)

                timeout = PROVIDER_TIMEOUTS.get(provider, 60.0)
                url = prov["url"]
                api_key = prov["key"]
                model_candidates = prov.get("models", [])
                last_error: Optional[str] = None

                # Attempt each model for this provider
                for model_for_provider in model_candidates:
                    result, err = await self._try_model(
                        provider=provider,
                        url=url,
                        api_key=api_key,
                        model=model_for_provider,
                        system=system,
                        prompt=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        response_format=response_format,
                        timeout=timeout,
                        attempt_count=2,
                        start=start,
                    )
                    if result is not None:
                        return result
                    last_error = err

                # All models for this provider failed
                h = self._health(provider)
                h["error_count"] += 1
                h["last_error"] = time.time()
                if h["error_count"] >= MAX_PROVIDER_ERRORS:
                    h["is_available"] = False
                log.warning("llm_provider_exhausted", provider=provider,
                            error=last_error, error_count=h["error_count"])

        raise RuntimeError("All configured LLM providers failed after retries")

    # ------------------------------------------------------------------
    # _try_model() — Single model attempt with retries
    # ------------------------------------------------------------------
    async def _try_model(
        self,
        provider: str,
        url: str,
        api_key: str,
        model: str,
        system: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        response_format: Optional[str],
        timeout: float,
        attempt_count: int,
        start: float,
    ) -> tuple[Optional[ModelResponse], Optional[str]]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://aegis.ai"
            headers["X-Title"] = "AEGIS Intelligence"

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if provider == "groq" and response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0)) as client:
            for attempt in range(attempt_count):
                try:
                    resp = await client.post(url, headers=headers, json=payload)

                    if resp.status_code == 200:
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"]

                        if response_format == "toon" and "confidence" not in content:
                            log.warning("llm_toon_validation_failed", provider=provider, model=model)
                            raise RuntimeError("TOON validation failed")

                        usage = data.get("usage", {})
                        latency = int((time.monotonic() - start) * 1000)
                        return ModelResponse(
                            content=content,
                            model=model,
                            input_tokens=usage.get("prompt_tokens", len(system + prompt) // 4),
                            output_tokens=usage.get("completion_tokens", len(content) // 4),
                            latency_ms=latency,
                            cost_usd=0.0,
                        ), None

                    if resp.status_code == 429:
                        retry_after = float(resp.headers.get("retry-after", "5"))
                        jitter = random.uniform(0.5, 1.5)
                        log.warning("llm_rate_limited", provider=provider, model=model,
                                    retry_after=retry_after, attempt=attempt)
                        if retry_after > 10.0:
                            # Do not block the pipeline for long rate-limit windows; fail over to next model candidate
                            return None, f"429 rate limit exceeded ({retry_after}s) on {provider}/{model}"
                        await asyncio.sleep(retry_after + jitter)
                        continue

                    # Non-200, non-429: raise_for_status to trigger retry
                    resp.raise_for_status()

                except httpx.ConnectError as e:
                    backoff = (2 ** attempt) + random.uniform(0.2, 1.0)
                    log.error("llm_connect_error", provider=provider, model=model,
                              attempt=attempt, backoff=backoff, error=str(e))
                    await asyncio.sleep(backoff)
                    continue

                except httpx.TimeoutException as e:
                    backoff = (2 ** attempt) + random.uniform(0.2, 1.0)
                    log.error("llm_timeout", provider=provider, model=model,
                              attempt=attempt, timeout=timeout, error=str(e))
                    await asyncio.sleep(backoff)
                    continue

                except Exception as e:
                    log.error("llm_provider_error", provider=provider, model=model,
                              attempt=attempt, error=str(e))
                    await asyncio.sleep(1.0 + random.uniform(0.2, 1.0))
                    continue

        return None, f"{provider}/{model} failed after {attempt_count} attempts"

    # ------------------------------------------------------------------
    # _build_providers() — Build provider list from env
    # ------------------------------------------------------------------
    def _build_providers(self) -> list[dict[str, Any]]:
        providers: list[dict[str, Any]] = []

        groq_key = os.getenv("GROQ_API_KEY", "")
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        openai_key = os.getenv("OPENAI_API_KEY", "")
        ollama_url = os.getenv("OLLAMA_API_URL", "")

        if groq_key:
            models = [m.strip() for m in os.getenv("GROQ_MODELS", GROQ_MODEL).split(",") if m.strip()]
            providers.append({"name": "groq", "url": GROQ_API_URL, "key": groq_key, "models": models})
        if openrouter_key:
            models = [m.strip() for m in os.getenv("OPENROUTER_MODELS", os.getenv("OPENROUTER_MODEL", OPENAI_MODEL)).split(",") if m.strip()]
            providers.append({"name": "openrouter", "url": OPENROUTER_API_URL, "key": openrouter_key, "models": models})
        if openai_key:
            models = [m.strip() for m in os.getenv("OPENAI_MODELS", OPENAI_MODEL).split(",") if m.strip()]
            providers.append({"name": "openai", "url": OPENAI_API_URL, "key": openai_key, "models": models})
        if ollama_url:
            models = [m.strip() for m in os.getenv("OLLAMA_MODELS", os.getenv("OLLAMA_MODEL", OLLAMA_MODEL)).split(",") if m.strip()]
            providers.append({"name": "ollama", "url": ollama_url, "key": "", "models": models})

        return providers

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
