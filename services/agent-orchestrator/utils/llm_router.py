"""
AEGIS LLM Router — Hugging Face Multi-Model Routing
Routes requests to Hugging Face models based on task type,
cost budget (free), latency requirements, and model capabilities.
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import httpx

log = structlog.get_logger()


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
class ModelResponse:
    content:       str
    model:         str
    input_tokens:  int = 0
    output_tokens: int = 0
    latency_ms:    int = 0
    cost_usd:      float = 0.0  # Always 0 for HF


# Which model to use per task
TASK_ROUTING: dict[TaskType, str] = {
    TaskType.SCRAPE_ANALYSIS: "microsoft/Phi-3-mini-4k-instruct",
    TaskType.FINANCIAL:       "microsoft/Phi-3-mini-4k-instruct",
    TaskType.DEBATE:          "microsoft/Phi-3-mini-4k-instruct",
    TaskType.SYNTHESIS:       "microsoft/Phi-3-mini-4k-instruct",
    TaskType.CRITIQUE:        "microsoft/Phi-3-mini-4k-instruct",
    TaskType.CLASSIFICATION:  "microsoft/Phi-3-mini-4k-instruct",
    TaskType.REPORT:          "microsoft/Phi-3-mini-4k-instruct",
    TaskType.EMBEDDING:       "sentence-transformers/all-MiniLM-L6-v2",
}


class LLMRouter:
    def __init__(self):
        self.models: dict[str, Any] = {}
        self.tokenizers: dict[str, Any] = {}
        self.pipelines: dict[str, Any] = {}
        self.embedding_model: Optional[Any] = None
        self.health: dict[str, dict] = {}  # Track model health
        
    async def complete(
        self,
        task_type: TaskType,
        system: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        response_format: Optional[str] = None,
    ) -> ModelResponse:
        model_name = TASK_ROUTING[task_type]
        
        try:
            start = time.monotonic()
            response = await self._call(model_name, system, prompt, max_tokens, temperature, response_format)
            latency = int((time.monotonic() - start) * 1000)
            
            # Update health
            if model_name not in self.health:
                self.health[model_name] = {"error_count": 0, "last_error": 0.0, "avg_latency": 0.0, "is_available": True}
            
            h = self.health[model_name]
            h["avg_latency"] = (h["avg_latency"] * 0.9) + (latency * 0.1)
            h["error_count"] = max(0, h["error_count"] - 1)
            
            log.info("llm_call_success", model=model_name,
                     tokens=response.input_tokens + response.output_tokens, latency_ms=latency)
            return response
            
        except Exception as exc:
            if model_name not in self.health:
                self.health[model_name] = {"error_count": 0, "last_error": 0.0, "avg_latency": 0.0, "is_available": True}
            
            h = self.health[model_name]
            h["error_count"] += 1
            h["last_error"] = time.time()
            if h["error_count"] > 5:
                h["is_available"] = False
            
            log.error("llm_call_failed", model=model_name, error=str(exc))
            raise
    
    async def _call(
        self, model_name: str, system: str, prompt: str,
        max_tokens: int, temperature: float, response_format: Optional[str],
    ) -> ModelResponse:
        start = time.monotonic()
        
        if model_name == TASK_ROUTING[TaskType.EMBEDDING]:
            raise ValueError("Embedding model should not be called via _call")
        
        # Format prompt with system message
        formatted_prompt = f"<|system|>\n{system}<|end|>\n<|user|>\n{prompt}<|end|>\n<|assistant|>"
        
        if response_format == "json":
            formatted_prompt += "\nPlease respond with valid JSON only."
        elif response_format == "toon":
            formatted_prompt += "\nPlease respond with valid TOON (Token-Oriented Object Notation) only."
        
        headers = {}
        token = os.getenv("HF_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        payload = {
            "inputs": formatted_prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "return_full_text": False
            }
        }
        
        content = ""
        async with httpx.AsyncClient(timeout=120.0) as client:
            for attempt in range(6):
                try:
                    resp = await client.post(
                        f"https://api-inference.huggingface.co/models/{model_name}",
                        headers=headers,
                        json=payload
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, list) and len(data) > 0:
                            content = data[0].get("generated_text", "")
                        else:
                            content = str(data)
                        break
                    elif resp.status_code == 503:
                        err_data = resp.json()
                        estimated_time = err_data.get("estimated_time", 10.0)
                        log.warning("hf_model_loading", model=model_name, wait_seconds=estimated_time)
                        await asyncio.sleep(min(estimated_time, 15.0))
                    else:
                        resp.raise_for_status()
                except Exception as e:
                    if attempt == 5:
                        raise e
                    await asyncio.sleep(2.0)
                    
        in_tok = len(formatted_prompt) // 4
        out_tok = len(content) // 4 if content else 0
        latency = int((time.monotonic() - start) * 1000)
        
        return ModelResponse(
            content=content,
            model=model_name,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency,
            cost_usd=0.0,
        )
    
    async def embed(self, text: str) -> list[float]:
        """Generate embeddings using serverless Hugging Face Inference API."""
        embedding_model_name = TASK_ROUTING[TaskType.EMBEDDING]
        start = time.monotonic()
        
        headers = {}
        token = os.getenv("HF_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        payload = {
            "inputs": text[:8000]
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(6):
                try:
                    resp = await client.post(
                        f"https://api-inference.huggingface.co/models/{embedding_model_name}",
                        headers=headers,
                        json=payload
                    )
                    if resp.status_code == 200:
                        res = resp.json()
                        if isinstance(res, list):
                            if len(res) > 0 and isinstance(res[0], list):
                                return res[0]
                            return res
                        raise ValueError(f"Unexpected embedding response format: {res}")
                    elif resp.status_code == 503:
                        err_data = resp.json()
                        estimated_time = err_data.get("estimated_time", 10.0)
                        log.warning("hf_model_loading", model=embedding_model_name, wait_seconds=estimated_time)
                        await asyncio.sleep(min(estimated_time, 15.0))
                    else:
                        resp.raise_for_status()
                except Exception as e:
                    if attempt == 5:
                        raise e
                    await asyncio.sleep(2.0)
                    
    def get_provider(self, name: str):
        return name