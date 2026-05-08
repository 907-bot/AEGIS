"""
AEGIS Experience Bank — Few-Shot Learning Memory System
Stores successful reasoning traces and retrieves similar ones via cosine similarity.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

import structlog

from utils.db import get_db_pool
from utils.llm_router import LLMRouter

log = structlog.get_logger()


class ExperienceBank:
    """
    Vector-based few-shot experience storage.
    Implements diversity-aware selection (MMR) to avoid redundant examples.
    """

    def __init__(self):
        self._router: Optional[LLMRouter] = None

    def _get_router(self) -> LLMRouter:
        if not self._router:
            self._router = LLMRouter()
        return self._router

    async def store_experience(
        self,
        investigation_id: str,
        task_type: str,
        input_text: str,
        reasoning: str,
        output: dict,
        outcome: str = "success",
        user_feedback: Optional[int] = None,
    ) -> None:
        """Store a completed investigation as a few-shot example."""
        try:
            embedding = await self._get_router().embed(input_text)
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO experiences
                       (id, investigation_id, task_type, input_embedding,
                        input_text, reasoning, output, outcome, user_feedback)
                       VALUES($1,$2,$3,$4::vector,$5,$6,$7::jsonb,$8,$9)""",
                    str(uuid.uuid4()),
                    investigation_id,
                    task_type,
                    json.dumps(embedding),
                    input_text[:1000],
                    reasoning[:2000],
                    json.dumps(output),
                    outcome,
                    user_feedback,
                )
            log.info("experience_stored", task_type=task_type, outcome=outcome)
        except Exception as e:
            log.error("experience_store_failed", error=str(e))

    async def retrieve_similar(
        self,
        input_text: str,
        task_type: str,
        k: int = 3,
        outcome_filter: str = "success",
    ) -> list[dict]:
        """
        Retrieve top-k similar experiences using cosine similarity.
        Uses Maximal Marginal Relevance (MMR) for diversity.
        """
        try:
            query_embedding = await self._get_router().embed(input_text)
            embedding_str = json.dumps(query_embedding)
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT input_text, reasoning, output, outcome, user_feedback,
                              1 - (input_embedding <=> $1::vector) AS similarity
                       FROM experiences
                       WHERE task_type=$2
                         AND outcome=$3
                         AND input_embedding IS NOT NULL
                       ORDER BY input_embedding <=> $1::vector
                       LIMIT $4""",
                    embedding_str, task_type, outcome_filter, k * 3,
                )

            if not rows:
                return []

            # Convert to dicts
            candidates = [
                {
                    "input_text":    r["input_text"],
                    "reasoning":     r["reasoning"],
                    "output":        json.loads(r["output"]) if r["output"] else {},
                    "similarity":    float(r["similarity"]),
                    "confidence":    float(r.get("user_feedback") or 3) / 5,
                }
                for r in rows
            ]

            # MMR diversity selection
            return self._mmr_select(candidates, k, lambda_=0.7)

        except Exception as e:
            log.error("experience_retrieve_failed", error=str(e))
            return []

    def _mmr_select(self, candidates: list[dict], k: int, lambda_: float = 0.7) -> list[dict]:
        """
        Maximal Marginal Relevance: balance relevance vs diversity.
        λ=1 → pure relevance, λ=0 → pure diversity
        """
        if not candidates or k <= 0:
            return []

        selected = [candidates[0]]
        remaining = candidates[1:]

        while len(selected) < k and remaining:
            best_score = -float("inf")
            best_cand  = None

            for cand in remaining:
                relevance = cand["similarity"]
                max_sim_to_selected = max(
                    self._text_similarity(cand["input_text"], s["input_text"])
                    for s in selected
                )
                mmr_score = lambda_ * relevance - (1 - lambda_) * max_sim_to_selected
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_cand  = cand

            if best_cand:
                selected.append(best_cand)
                remaining.remove(best_cand)

        return selected

    def _text_similarity(self, a: str, b: str) -> float:
        """Simple Jaccard similarity for diversity check."""
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)
