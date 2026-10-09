"""
Black-Box Validation Suite for AEGIS Adversarial Debate Chamber & Report Workflow.
Validates Bull, Bear, Skeptic, Synthesizer, and Consolidated Strategic Report generation.
"""
import pytest
import os
import json
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv("../../.env")

from utils.llm_router import LLMRouter
from debate.crew import AegisDebateCrew
from workflows.investigation import InvestigationWorkflow


@pytest.fixture(scope="module")
def llm_router():
    return LLMRouter()


@pytest.fixture(scope="module")
def sample_recon_results():
    """Realistic reconnaissance data from the 7 agents."""
    return [
        {
            "agent_type": "sentry",
            "status": "completed",
            "confidence": 0.90,
            "evidence": ["https://stripe.com", "Scraped 15000 chars"],
            "data": {
                "company_name": "Stripe",
                "tagline": "Financial infrastructure for the internet",
                "description": "Payment processing and financial infrastructure for online businesses",
                "business_model": "B2B SaaS / Payments",
                "industry": "Financial Technology",
                "tech_stack": {
                    "frontend": ["React"],
                    "analytics": ["Segment"],
                    "hosting": ["AWS"],
                    "payments": ["Stripe"]
                }
            }
        },
        {
            "agent_type": "financial_archaeologist",
            "status": "completed",
            "confidence": 0.85,
            "evidence": ["Pricing page", "Career page"],
            "data": {
                "revenue_stage": "$100M+",
                "valuation": "$65B",
                "funding_stage": "late",
                "hiring_velocity": "steady",
                "financial_health_score": 92,
                "engineering_ratio": 45,
                "sales_ratio": 25,
            }
        },
        {
            "agent_type": "tech_stack",
            "status": "completed",
            "confidence": 0.92,
            "evidence": ["HTML inspection"],
            "data": {
                "frontend": ["React", "Next.js"],
                "backend_inference": ["Ruby", "Go", "Java"],
                "infrastructure": ["AWS"],
                "databases_inferred": ["PostgreSQL", "MongoDB"],
                "innovation_score": 95,
                "tech_maturity": "enterprise",
            }
        },
        {
            "agent_type": "sentiment_scout",
            "status": "completed",
            "confidence": 0.88,
            "evidence": ["Press and reviews"],
            "data": {
                "overall_sentiment": "very_positive",
                "sentiment_score": 88,
                "brand_perception": "premium",
                "momentum": "accelerating"
            }
        },
        {
            "agent_type": "regulatory_radar",
            "status": "completed",
            "confidence": 0.80,
            "evidence": ["Terms and privacy policies"],
            "data": {
                "compliance_score": 94,
                "regulatory_risk_level": "medium",
                "data_handling": "clear",
                "jurisdictions_operating": ["US", "EU", "APAC"]
            }
        },
        {
            "agent_type": "competitive_cartographer",
            "status": "completed",
            "confidence": 0.85,
            "evidence": ["Market signals"],
            "data": {
                "direct_competitors": [
                    {"name": "Adyen", "threat_level": "high"},
                    {"name": "PayPal", "threat_level": "medium"}
                ],
                "market_position": "leader",
                "moat_score": 90,
                "competitive_risk_score": 35
            }
        },
        {
            "agent_type": "talent_flow",
            "status": "completed",
            "confidence": 0.82,
            "evidence": ["Team data"],
            "data": {
                "ceo": {"name": "Patrick Collison", "background": "Co-founder & CEO"},
                "team_quality_score": 96,
                "office_locations": ["San Francisco, CA"]
            }
        }
    ]


class TestDebateAndSynthesisValidation:
    """Validate data generation of Bull, Bear, Skeptic, Synthesizer, and final Report."""

    @pytest.mark.asyncio
    async def test_debate_crew_adversarial_outputs(self, llm_router, sample_recon_results):
        crew = AegisDebateCrew(llm_router)
        debate = await crew.run("bb-debate-01", sample_recon_results)

        # 1. Structural assertions
        for key in ["bull_thesis", "bear_thesis", "skeptic_analysis", "synthesis"]:
            assert key in debate, f"Debate result missing '{key}'"

        # 2. Bull Thesis assertions: non-trivial, affirmative growth arguments
        bull = debate["bull_thesis"]
        assert isinstance(bull, str)
        assert len(bull) > 200, "Bull thesis must be substantive (>200 chars)"
        assert not bull.startswith("..."), "Bull thesis cannot be stub"

        # 3. Bear Thesis assertions: non-trivial, risk and downside arguments
        bear = debate["bear_thesis"]
        assert isinstance(bear, str)
        assert len(bear) > 200, "Bear thesis must be substantive (>200 chars)"

        # 4. Skeptic Analysis assertions: meta-audit of biases and validity
        skeptic = debate["skeptic_analysis"]
        assert isinstance(skeptic, str)
        assert len(skeptic) > 150, "Skeptic audit must be substantive (>150 chars)"

        # 5. Synthesis assertions: structured resolution
        synth = debate["synthesis"]
        assert isinstance(synth, dict), "Synthesis must be parsed JSON dict"

        # Verify Synthesizer Schema
        assert "final_verdict" in synth, "Synthesizer must provide final_verdict"
        valid_verdicts = ["strong_buy", "buy", "hold", "watch", "avoid"]
        assert synth["final_verdict"].lower() in valid_verdicts, (
            f"Invalid final_verdict: {synth['final_verdict']}. Must be one of {valid_verdicts}"
        )

        assert "confidence_score" in synth
        assert 0.0 <= float(synth["confidence_score"]) <= 1.0

        for score_key in ["vitality_score", "moat_score", "risk_score"]:
            assert score_key in synth, f"Missing score '{score_key}' in synthesis"
            val = float(synth[score_key])
            assert 0 <= val <= 100, f"Score {score_key}={val} out of range [0, 100]"

        # Verify scenario probabilities sum to approximately 1.0 (100%)
        scenarios = synth.get("scenarios", {})
        if scenarios and all(k in scenarios for k in ["bull", "base", "bear"]):
            p_bull = float(scenarios["bull"].get("probability", 0.33))
            p_base = float(scenarios["base"].get("probability", 0.34))
            p_bear = float(scenarios["bear"].get("probability", 0.33))
            total_prob = p_bull + p_base + p_bear
            assert 0.85 <= total_prob <= 1.15, (
                f"Scenario probabilities do not sum to ~1.0: {total_prob} ({p_bull}, {p_base}, {p_bear})"
            )

    @pytest.mark.asyncio
    async def test_investigation_report_workflow_data_generation(self, llm_router, sample_recon_results):
        crew = AegisDebateCrew(llm_router)
        debate = await crew.run("bb-debate-02", sample_recon_results)

        workflow = InvestigationWorkflow(llm_router)
        report = await workflow.generate_report(
            "bb-inv-report-01",
            "https://stripe.com",
            debate,
            sample_recon_results
        )

        assert isinstance(report, dict), "Report must be a dictionary"

        # Check critical fields exist
        required_fields = [
            "company_name", "executive_summary", "bull_thesis", "bear_thesis",
            "skeptic_analysis", "final_verdict", "confidence_score", "vitality_score",
            "moat_score", "risk_score", "red_flag_matrix", "moat_analysis",
            "scenarios", "recommendations", "raw_markdown"
        ]
        for f in required_fields:
            assert f in report, f"Required field '{f}' missing from final report"

        # Verify non-stub executive summary
        summary = report["executive_summary"]
        assert isinstance(summary, str)
        assert len(summary) > 100, "Executive summary must be detailed (>100 chars)"

        # Verify raw markdown is multi-section
        markdown = report.get("raw_markdown", "")
        assert isinstance(markdown, str)
        assert len(markdown) > 300, "Raw markdown report must be substantial (>300 chars)"
