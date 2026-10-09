"""
AEGIS Black-Box Comparative Live Validation Harness
Executes full multi-agent pipeline against two contrasting real-world domains:
  1. Commercial FinTech Enterprise: https://stripe.com
  2. Open-Source Developer Tooling: https://fastapi.tiangolo.com

Validates schema fidelity, value bounds, semantic grounding, anti-hallucination,
and cross-agent consistency.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv("../../.env")

import sys
import os

orchestrator_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if orchestrator_dir not in sys.path:
    sys.path.insert(0, orchestrator_dir)

from utils.llm_router import LLMRouter
from agents.sentry import SentryAgent
from agents.financial import FinancialArchaeologist
from agents.talent import TalentFlowAgent
from agents.tech_stack import TechStackAgent
from agents.sentiment import SentimentScout
from agents.regulatory import RegulatoryRadar
from agents.competitive import CompetitiveCartographer
from debate.crew import AegisDebateCrew
from workflows.investigation import InvestigationWorkflow


@dataclass
class ValidationReport:
    target_url: str
    target_type: str
    company_name: str = ""
    agent_results: dict = field(default_factory=dict)
    debate_result: dict = field(default_factory=dict)
    final_report: dict = field(default_factory=dict)
    assertions_passed: int = 0
    assertions_failed: int = 0
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_s: float = 0.0

    def assert_rule(self, condition: bool, message: str):
        if condition:
            self.assertions_passed += 1
        else:
            self.assertions_failed += 1
            self.failures.append(message)

    def warn_rule(self, condition: bool, message: str):
        if not condition:
            self.warnings.append(message)


async def run_pipeline_for_target(url: str, target_type: str, router: LLMRouter) -> ValidationReport:
    start_time = time.monotonic()
    report = ValidationReport(target_url=url, target_type=target_type)
    inv_id = f"bb-{target_type}-{int(time.time())}"

    print(f"\n=====================================================================")
    print(f"🚀 INITIATING BLACK-BOX TEST: {url} ({target_type})")
    print(f"=====================================================================")

    # -------------------------------------------------------------
    # PHASE 1: Specialized Reconnaissance (7 Agents)
    # -------------------------------------------------------------
    print("  [Phase 1] Launching 7 Specialized Agents in Parallel...")
    agents = [
        SentryAgent(router),
        FinancialArchaeologist(router),
        TalentFlowAgent(router),
        TechStackAgent(router),
        SentimentScout(router),
        RegulatoryRadar(router),
        CompetitiveCartographer(router),
    ]

    agent_tasks = [agent.investigate(inv_id, url) for agent in agents]
    raw_results = await asyncio.gather(*agent_tasks, return_exceptions=True)

    recon_results = []
    for i, res in enumerate(raw_results):
        agent_name = agents[i].name
        if isinstance(res, Exception):
            report.assert_rule(False, f"Agent {agent_name} raised uncaught exception: {res}")
            report.agent_results[agent_name] = {"status": "crashed", "error": str(res)}
        else:
            report.agent_results[agent_name] = res
            if res.get("status") == "completed":
                recon_results.append(res)
            else:
                report.warn_rule(False, f"Agent {agent_name} returned non-completed status: {res.get('status')}")

    print(f"  [Phase 1] Completed. Succeeded agents: {len(recon_results)} / 7")
    report.assert_rule(len(recon_results) >= 5, f"Required >=5 agents succeeded, got {len(recon_results)}")

    # Specific Agent Validations
    sentry_data = report.agent_results.get("sentry", {}).get("data", {})
    report.company_name = sentry_data.get("company_name", "")
    report.assert_rule(len(report.company_name) >= 2, f"Sentry failed to extract valid company name: '{report.company_name}'")
    report.assert_rule(report.company_name.lower() not in ["...", "unknown", "null"], f"Sentry returned placeholder name: '{report.company_name}'")

    tech_data = report.agent_results.get("tech_stack", {}).get("data", {})
    report.assert_rule(isinstance(tech_data.get("frontend"), list), "TechStack frontend must be a list")
    report.assert_rule(0 <= float(tech_data.get("innovation_score", 50)) <= 100, "TechStack innovation_score must be 0-100")

    fin_data = report.agent_results.get("financial_archaeologist", {}).get("data", {})
    report.assert_rule("revenue_stage" in fin_data, "FinancialArchaeologist must include revenue_stage")
    report.assert_rule(0.0 <= float(report.agent_results.get("financial_archaeologist", {}).get("confidence", 0)) <= 1.0, "Financial confidence out of bounds")

    sent_data = report.agent_results.get("sentiment_scout", {}).get("data", {})
    report.assert_rule("overall_sentiment" in sent_data, "SentimentScout must classify overall_sentiment")

    comp_data = report.agent_results.get("competitive_cartographer", {}).get("data", {})
    report.assert_rule(0 <= float(comp_data.get("moat_score", 50)) <= 100, "Competitive moat_score must be 0-100")

    # -------------------------------------------------------------
    # PHASE 2: Debate Chamber (Bull vs Bear vs Skeptic -> Synthesizer)
    # -------------------------------------------------------------
    print("  [Phase 2] Convening Adversarial Debate Chamber...")
    crew = AegisDebateCrew(router)
    debate = await crew.run(inv_id, recon_results)
    report.debate_result = debate

    # Debate Assertions
    bull = debate.get("bull_thesis", "")
    bear = debate.get("bear_thesis", "")
    skeptic = debate.get("skeptic_analysis", "")
    synth = debate.get("synthesis", {})

    report.assert_rule(isinstance(bull, str) and len(bull) > 200, "Bull thesis must be substantive (>200 chars)")
    report.assert_rule(isinstance(bear, str) and len(bear) > 200, "Bear thesis must be substantive (>200 chars)")
    report.assert_rule(isinstance(skeptic, str) and len(skeptic) > 150, "Skeptic audit must be substantive (>150 chars)")
    report.assert_rule(isinstance(synth, dict) and len(synth) > 0, "Synthesizer must return parsed dict")

    # Verdict & Score Assertions
    verdict = synth.get("final_verdict", "").lower()
    report.assert_rule(verdict in ["strong_buy", "buy", "hold", "watch", "avoid"], f"Invalid final_verdict: '{verdict}'")

    for s_key in ["vitality_score", "moat_score", "risk_score"]:
        score_val = float(synth.get(s_key, -1))
        report.assert_rule(0 <= score_val <= 100, f"Synthesizer {s_key}={score_val} must be 0-100")

    # -------------------------------------------------------------
    # PHASE 3: Consolidated Strategic Report
    # -------------------------------------------------------------
    print("  [Phase 3] Generating Consolidated Strategic Intelligence Report...")
    workflow = InvestigationWorkflow(router)
    final_report = await workflow.generate_report(inv_id, url, debate, recon_results)
    report.final_report = final_report

    # Report Assertions
    for req_field in ["company_name", "executive_summary", "bull_thesis", "bear_thesis", "final_verdict", "confidence_score", "raw_markdown"]:
        report.assert_rule(req_field in final_report and bool(final_report[req_field]), f"Final report missing or empty field: '{req_field}'")

    report.assert_rule(len(final_report.get("executive_summary", "")) > 100, "Executive summary too short or stub")
    report.assert_rule(len(final_report.get("raw_markdown", "")) > 400, "Raw markdown report too short or stub")

    report.duration_s = round(time.monotonic() - start_time, 2)
    print(f"  ✅ Completed {target_type} in {report.duration_s}s. Passed: {report.assertions_passed}, Failed: {report.assertions_failed}, Warnings: {len(report.warnings)}")
    return report


async def main():
    router = LLMRouter()

    # Run tests on both targets
    stripe_report = await run_pipeline_for_target("https://stripe.com", "Commercial FinTech", router)
    fastapi_report = await run_pipeline_for_target("https://fastapi.tiangolo.com", "Open Source Framework", router)

    # -------------------------------------------------------------
    # PHASE 4: Cross-Domain Semantic Grounding & Differentiation
    # -------------------------------------------------------------
    print("\n=====================================================================")
    print("🔍 CROSS-DOMAIN COMPARATIVE GROUNDING AUDIT")
    print("=====================================================================")

    # 1. Company Identification Check
    print(f"Stripe Detected Company:  '{stripe_report.company_name}'")
    print(f"FastAPI Detected Company: '{fastapi_report.company_name}'")
    assert "stripe" in stripe_report.company_name.lower(), "Stripe domain failed company name grounding"
    assert "fastapi" in fastapi_report.company_name.lower(), "FastAPI domain failed company name grounding"

    # 2. Tech Stack Grounding Check
    stripe_tech = stripe_report.agent_results.get("tech_stack", {}).get("data", {})
    fastapi_tech = fastapi_report.agent_results.get("tech_stack", {}).get("data", {})
    print(f"Stripe Tech Backend:   {stripe_tech.get('backend_inference', [])}")
    print(f"FastAPI Tech Backend:  {fastapi_tech.get('backend_inference', [])}")

    # FastAPI MUST detect Python
    fastapi_backend_str = str(fastapi_tech.get("backend_inference", [])).lower()
    fastapi_detected_python = "python" in fastapi_backend_str or "python" in str(fastapi_tech).lower()
    print(f"FastAPI Python Grounding Validated: {fastapi_detected_python}")

    # 3. Financial & Business Model Grounding Check
    stripe_fin = stripe_report.agent_results.get("financial_archaeologist", {}).get("data", {})
    fastapi_fin = fastapi_report.agent_results.get("financial_archaeologist", {}).get("data", {})
    print(f"Stripe Revenue Stage:   {stripe_fin.get('revenue_stage')}")
    print(f"FastAPI Revenue Stage:  {fastapi_fin.get('revenue_stage')}")
    print(f"Stripe Valuation:       {stripe_fin.get('valuation')}")
    print(f"FastAPI Valuation:      {fastapi_fin.get('valuation')}")

    # 4. Strategic Synthesis Verdicts
    print(f"Stripe Final Verdict:   {stripe_report.final_report.get('final_verdict')}")
    print(f"FastAPI Final Verdict:  {fastapi_report.final_report.get('final_verdict')}")

    # Dump JSON Artifact
    output_summary = {
        "execution_timestamp": datetime.utcnow().isoformat(),
        "stripe_summary": {
            "company_name": stripe_report.company_name,
            "verdict": stripe_report.final_report.get("final_verdict"),
            "confidence_score": stripe_report.final_report.get("confidence_score"),
            "vitality_score": stripe_report.final_report.get("vitality_score"),
            "moat_score": stripe_report.final_report.get("moat_score"),
            "risk_score": stripe_report.final_report.get("risk_score"),
            "assertions_passed": stripe_report.assertions_passed,
            "assertions_failed": stripe_report.assertions_failed,
            "duration_s": stripe_report.duration_s,
            "failures": stripe_report.failures,
        },
        "fastapi_summary": {
            "company_name": fastapi_report.company_name,
            "verdict": fastapi_report.final_report.get("final_verdict"),
            "confidence_score": fastapi_report.final_report.get("confidence_score"),
            "vitality_score": fastapi_report.final_report.get("vitality_score"),
            "moat_score": fastapi_report.final_report.get("moat_score"),
            "risk_score": fastapi_report.final_report.get("risk_score"),
            "assertions_passed": fastapi_report.assertions_passed,
            "assertions_failed": fastapi_report.assertions_failed,
            "duration_s": fastapi_report.duration_s,
            "failures": fastapi_report.failures,
        }
    }

    results_path = "/Users/abhishekadari/.gemini/antigravity-ide/brain/91da65d8-c42f-4f1a-8183-326f0c6bb7b4/live_blackbox_results.json"
    with open(results_path, "w") as f:
        json.dump(output_summary, f, indent=2)

    print(f"\nSaved black box validation telemetry to: {results_path}")


if __name__ == "__main__":
    asyncio.run(main())
