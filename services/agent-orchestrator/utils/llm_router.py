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

import structlog
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from sentence_transformers import SentenceTransformer
import torch

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
# Using capable, free Hugging Face models
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
        self.embedding_model: Optional[SentenceTransformer] = None
        
        # Initialize models lazily to save memory
        self._initialize_embedding_model()
        
        self.health: dict[str, dict] = {}  # Track model health
    
    def _get_model(self, model_name: str):
        """Lazy load model and tokenizer."""
        if model_name not in self.models:
            log.info("loading_hf_model", model=model_name)
            try:
                # For text generation models
                if "embed" not in model_name.lower():
                    tokenizer = AutoTokenizer.from_pretrained(model_name)
                    model = AutoModelForCausalLM.from_pretrained(
                        model_name,
                        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                        device_map="auto" if torch.cuda.is_available() else None,
                    )
                    
                    # Set pad token if not present
                    if tokenizer.pad_token is None:
                        tokenizer.pad_token = tokenizer.eos_token
                    
                    self.models[model_name] = model
                    self.tokenizers[model_name] = tokenizer
                    
                    # Create pipeline
                    self.pipelines[model_name] = pipeline(
                        "text-generation",
                        model=model,
                        tokenizer=tokenizer,
                        max_new_tokens=2048,
                        do_sample=True,
                        temperature=0.7,
                        device_map="auto" if torch.cuda.is_available() else None,
                        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    )
                else:
                    # This is an embedding model, handled separately
                    pass
            except Exception as e:
                log.error("failed_to_load_hf_model", model=model_name, error=str(e))
                raise
        
        return self.models.get(model_name), self.tokenizers.get(model_name), self.pipelines.get(model_name)
    
    def _initialize_embedding_model(self):
        """Initialize the embedding model."""
        embedding_model_name = TASK_ROUTING[TaskType.EMBEDDING]
        try:
            log.info("loading_embedding_model", model=embedding_model_name)
            self.embedding_model = SentenceTransformer(embedding_model_name)
        except Exception as e:
            log.error("failed_to_load_embedding_model", model=embedding_model_name, error=str(e))
            raise
    
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
            
            # Update health (simplified)
            if model_name not in self.health:
                self.health[model_name] = {"error_count": 0, "last_error": 0.0, "avg_latency": 0.0, "is_available": True}
            
            h = self.health[model_name]
            h.avg_latency = (h.avg_latency * 0.9) + (latency * 0.1)
            h.error_count = max(0, h.error_count - 1)
            
            log.info("llm_call_success", model=model_name,
                     tokens=response.input_tokens + response.output_tokens, latency_ms=latency)
            return response
            
        except Exception as exc:
            # Update health
            if model_name not in self.health:
                self.health[model_name] = {"error_count": 0, "last_error": 0.0, "avg_latency": 0.0, "is_available": True}
            
            h = self.health[model_name]
            h.error_count += 1
            h.last_error = time.time()
            if h.error_count > 5:
                h.is_available = False
                # In a real scenario, we might try to reload or switch models
                # For simplicity, we'll just log and continue trying
                asyncio.create_task(self._restore_model(model_name))
            
            log.error("llm_call_failed", model=model_name, error=str(exc))
            raise
    
    async def _call(
        self, model_name: str, system: str, prompt: str,
        max_tokens: int, temperature: float, response_format: Optional[str],
    ) -> ModelResponse:
        start = time.monotonic()
        
        # Get model components
        model, tokenizer, pipe = self._get_model(model_name)
        
        if model_name == TASK_ROUTING[TaskType.EMBEDDING]:
            # This shouldn't happen as embeddings are handled separately
            raise ValueError("Embedding model should not be called via _call")
        
        # Format prompt with system message
        formatted_prompt = f"<|system|>\n{system}<|end|>\n<|user|>\n{prompt}<|end|>\n<|assistant|>"
        
        # Generation config
        generation_kwargs = {
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "do_sample": True,
            "pad_token_id": tokenizer.eos_token_id,
            "return_full_text": False,  # Only return generated text
        }
        
        if response_format == "json":
            # Add JSON formatting instruction
            formatted_prompt += "\nPlease respond with valid JSON only."
        
        # Generate text
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: pipe(formatted_prompt, **generation_kwargs)
            )
            
            content = result[0]["generated_text"] if result else ""
            
            # Simple token estimation (more accurate would require tokenizer)
            in_tok = len(tokenizer.encode(formatted_prompt))
            out_tok = len(tokenizer.encode(content)) if content else 0
            
        except Exception as e:
            log.error("hf_generation_failed", model=model_name, error=str(e))
            raise
        
        latency = int((time.monotonic() - start) * 1000)
        
        return ModelResponse(
            content=content,
            model=model_name,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency,
            cost_usd=0.0,  # Free with HF
        )
    
    async def embed(self, text: str) -> list[float]:
        """Generate embeddings using sentence transformers."""
        if self.embedding_model is None:
            self._initialize_embedding_model()
        
        start = time.monotonic()
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None,
                lambda: self.embedding_model.encode(text[:8000])  # Limit text length
            )
            latency = int((time.monotonic() - start) * 1000)
            
            return embedding.tolist()
        except Exception as e:
            log.error("embedding_failed", error=str(e))
            raise
    
    async def _restore_model(self, model_name: str, delay: int = 60):
        """Attempt to restore a model after errors."""
        await asyncio.sleep(delay)
        try:
            # Clear the model from cache to force reload
            if model_name in self.models:
                del self.models[model_name]
            if model_name in self.tokenizers:
                del self.tokenizers[model_name]
            if model_name in self.pipelines:
                del self.pipelines[model_name]
            
            # Try to reload
            self._get_model(model_name)
            
            # Update health
            if model_name in self.health:
                self.health[model_name].is_available = True
                self.health[model_name].error_count = 0
            
            log.info("model_restored", model=model_name)
        except Exception as e:
            log.error("model_restore_failed", model=model_name, error=str(e))
    
    def get_provider(self, name: str):
        """For CrewAI compatibility — returns model name string."""
        return name