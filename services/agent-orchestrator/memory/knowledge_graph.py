"""
AEGIS Knowledge Graph Service — Neo4j entity/relationship management.
Extracts entities from agent results and builds a queryable intelligence graph.
"""
from __future__ import annotations

import json
import os
from typing import Optional

import structlog
from neo4j import AsyncGraphDatabase, AsyncDriver

log = structlog.get_logger()


class KnowledgeGraphService:
    def __init__(self):
        self._driver: Optional[AsyncDriver] = None

    async def connect(self) -> None:
        uri = os.getenv("NEO4J_URL", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        pwd  = os.getenv("NEO4J_PASSWORD", "password")
        try:
            self._driver = AsyncGraphDatabase.driver(uri, auth=(user, pwd))
            await self._driver.verify_connectivity()
            await self._setup_schema()
            log.info("neo4j_connected", uri=uri)
        except Exception as e:
            log.warning("neo4j_unavailable", error=str(e))
            self._driver = None

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()

    async def _setup_schema(self) -> None:
        if not self._driver:
            return
        async with self._driver.session() as session:
            await session.run("CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE")
            await session.run("CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE")
            await session.run("CREATE CONSTRAINT tech_id IF NOT EXISTS FOR (t:Technology) REQUIRE t.id IS UNIQUE")
            await session.run("CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name)")

    async def populate(self, investigation_id: str, agent_results: list[dict]) -> None:
        if not self._driver:
            return
        try:
            company_data = self._extract_company(agent_results)
            competitors  = self._extract_competitors(agent_results)
            technologies = self._extract_technologies(agent_results)
            people       = self._extract_people(agent_results)

            async with self._driver.session() as session:
                # Upsert company node
                await session.run(
                    """MERGE (c:Company {id: $id})
                       SET c.name=$name, c.url=$url, c.industry=$industry,
                           c.investigation_id=$inv_id, c.updated_at=datetime()""",
                    id=investigation_id,
                    name=company_data.get("company_name", "Unknown"),
                    url=company_data.get("raw_url", ""),
                    industry=company_data.get("industry", ""),
                    inv_id=investigation_id,
                )

                # Competitors
                for comp in competitors[:5]:
                    await session.run(
                        """MERGE (c2:Company {id: $comp_id})
                           SET c2.name=$name, c2.url=$url
                           WITH c2
                           MATCH (c1:Company {id: $inv_id})
                           MERGE (c1)-[r:COMPETES_WITH {confidence: $conf}]->(c2)""",
                        comp_id=f"comp_{comp.get('name','').replace(' ','')}",
                        name=comp.get("name", ""),
                        url=comp.get("url", ""),
                        inv_id=investigation_id,
                        conf=comp.get("similarity", 70) / 100,
                    )

                # Technologies
                for tech in technologies[:10]:
                    await session.run(
                        """MERGE (t:Technology {id: $tech_id})
                           SET t.name=$name, t.category=$category
                           WITH t
                           MATCH (c:Company {id: $inv_id})
                           MERGE (c)-[:USES_TECHNOLOGY {confidence: 0.8}]->(t)""",
                        tech_id=f"tech_{tech.get('name','').replace(' ','')}",
                        name=tech.get("name", ""),
                        category=tech.get("category", ""),
                        inv_id=investigation_id,
                    )

                # People
                for person in people[:5]:
                    await session.run(
                        """MERGE (p:Person {id: $person_id})
                           SET p.name=$name, p.role=$role
                           WITH p
                           MATCH (c:Company {id: $inv_id})
                           MERGE (p)-[:WORKS_AT {role: $role}]->(c)""",
                        person_id=f"person_{person.get('name','').replace(' ','')}",
                        name=person.get("name", ""),
                        role=person.get("role", ""),
                        inv_id=investigation_id,
                    )

            log.info("knowledge_graph_populated", investigation_id=investigation_id)
        except Exception as e:
            log.error("knowledge_graph_error", error=str(e))

    async def get_snapshot(self, investigation_id: str) -> str:
        """Return graph as JSON for frontend visualization."""
        if not self._driver:
            return json.dumps({"nodes": [], "edges": []})
        try:
            async with self._driver.session() as session:
                result = await session.run(
                    """MATCH (c:Company {id: $id})-[r]-(n)
                       RETURN c, r, n LIMIT 50""",
                    id=investigation_id
                )
                records = await result.data()

            nodes: dict[str, dict] = {}
            edges: list[dict] = []

            for record in records:
                src = record.get("c", {})
                rel = record.get("r", {})
                tgt = record.get("n", {})

                for node in [src, tgt]:
                    if node and "id" in node:
                        nodes[node["id"]] = {
                            "id": node["id"],
                            "label": node.get("name", node["id"]),
                            "type": list(node.labels)[0] if hasattr(node, "labels") else "Entity",
                        }

                if rel:
                    edges.append({
                        "source":     investigation_id,
                        "target":     tgt.get("id", ""),
                        "label":      type(rel).__name__,
                        "confidence": rel.get("confidence", 0.5),
                    })

            return json.dumps({"nodes": list(nodes.values()), "edges": edges})
        except Exception as e:
            log.error("graph_snapshot_failed", error=str(e))
            return json.dumps({"nodes": [], "edges": []})

    # ─── Extraction helpers ───────────────────────────────────────────────
    def _extract_company(self, results: list[dict]) -> dict:
        for r in results:
            if r.get("agent_type") == "sentry" and r.get("status") == "completed":
                return r.get("data", {})
        return {}

    def _extract_competitors(self, results: list[dict]) -> list[dict]:
        for r in results:
            if r.get("agent_type") == "competitive_cartographer":
                return r.get("data", {}).get("direct_competitors", [])
        return []

    def _extract_technologies(self, results: list[dict]) -> list[dict]:
        for r in results:
            if r.get("agent_type") == "tech_stack":
                data = r.get("data", {})
                techs = []
                for cat, items in data.items():
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, str):
                                techs.append({"name": item, "category": cat})
                return techs
        return []

    def _extract_people(self, results: list[dict]) -> list[dict]:
        for r in results:
            if r.get("agent_type") == "talent_flow":
                names = r.get("data", {}).get("leadership_names", [])
                return [{"name": n, "role": "Leadership"} for n in names if isinstance(n, str)]
        return []
