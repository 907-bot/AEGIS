"""
AEGIS Prompt Genetic Algorithm — Evolve prompts across generations.
Uses tournament selection, crossover, and mutation to improve prompt fitness.
"""
from __future__ import annotations
import asyncio, json, random, uuid
from dataclasses import dataclass, field
from typing import Optional
import structlog
from utils.llm_router import LLMRouter, TaskType

log = structlog.get_logger()

@dataclass
class Prompt:
    id:         str   = field(default_factory=lambda: str(uuid.uuid4())[:8])
    content:    str   = ""
    generation: int   = 0
    fitness:    float = 0.0
    parent_ids: list  = field(default_factory=list)

class PromptGeneticAlgorithm:
    def __init__(self, llm: LLMRouter, population_size: int = 10, generations: int = 5, mutation_rate: float = 0.3):
        self.llm             = llm
        self.population_size = population_size
        self.generations     = generations
        self.mutation_rate   = mutation_rate

    async def evolve(self, task: str, seed_prompts: list[str]) -> Prompt:
        population = [Prompt(content=p, generation=0) for p in seed_prompts[:self.population_size]]
        for gen in range(self.generations):
            for prompt in population:
                if prompt.fitness == 0.0:
                    prompt.fitness = await self._evaluate(prompt.content, task)
            parents  = self._tournament_select(population, k=3)
            offspring = []
            for i in range(0, len(parents) - 1, 2):
                c1, c2 = self._crossover(parents[i], parents[i+1])
                offspring.extend([c1, c2])
            for child in offspring:
                if random.random() < self.mutation_rate:
                    child = await self._mutate(child, task)
            population = self._elitism(population, offspring)
            log.info("ga_generation", gen=gen, best_fitness=max(p.fitness for p in population))
        return max(population, key=lambda p: p.fitness)

    async def _evaluate(self, prompt: str, task: str) -> float:
        try:
            resp = await self.llm.complete(TaskType.CLASSIFICATION, "Rate this prompt quality 0-100 as JSON: {score: N}", f"Task: {task}\nPrompt: {prompt[:500]}", 100, 0.1, "json")
            data = json.loads(resp.content)
            return float(data.get("score", 50)) / 100
        except Exception:
            return 0.5

    def _tournament_select(self, population: list[Prompt], k: int = 3) -> list[Prompt]:
        selected = []
        for _ in range(len(population)):
            tournament = random.sample(population, min(k, len(population)))
            selected.append(max(tournament, key=lambda p: p.fitness))
        return selected

    def _crossover(self, p1: Prompt, p2: Prompt) -> tuple[Prompt, Prompt]:
        words1, words2 = p1.content.split(), p2.content.split()
        if len(words1) < 2 or len(words2) < 2:
            return p1, p2
        pt1 = random.randint(1, max(1, len(words1)-1))
        pt2 = random.randint(1, max(1, len(words2)-1))
        c1 = Prompt(content=" ".join(words1[:pt1] + words2[pt2:]), generation=p1.generation+1, parent_ids=[p1.id, p2.id])
        c2 = Prompt(content=" ".join(words2[:pt2] + words1[pt1:]), generation=p2.generation+1, parent_ids=[p1.id, p2.id])
        return c1, c2

    async def _mutate(self, prompt: Prompt, task: str) -> Prompt:
        try:
            resp = await self.llm.complete(TaskType.CLASSIFICATION, "You improve AI prompts. Return only the improved prompt text, nothing else.",
                f"Improve this prompt for task '{task}':\n{prompt.content[:800]}", 500, 0.8)
            return Prompt(content=resp.content.strip(), generation=prompt.generation, parent_ids=[prompt.id])
        except Exception:
            return prompt

    def _elitism(self, population: list[Prompt], offspring: list[Prompt]) -> list[Prompt]:
        combined = population + offspring
        combined.sort(key=lambda p: p.fitness, reverse=True)
        return combined[:self.population_size]
