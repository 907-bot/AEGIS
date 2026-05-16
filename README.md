# AEGIS 🧠
### Autonomous Multi-Agent Strategic Intelligence & Decision Orchestration Platform

[![Deploy Frontend](https://github.com/your-org/aegis/actions/workflows/deploy-frontend.yml/badge.svg)](https://github.com/your-org/aegis/actions)
[![Deploy Backend](https://github.com/your-org/aegis/actions/workflows/deploy-backend.yml/badge.svg)](https://github.com/your-org/aegis/actions)

> Drop any company URL → 7 AI agents investigate → Adversarial Bull/Bear/Skeptic debate → Institutional-grade strategic report in **4-6 minutes**

---

## Tech Stack

| Layer        | Technology                                              |
|--------------|---------------------------------------------------------|
| Frontend     | Next.js 14 · TypeScript · Tailwind CSS · Socket.IO      |
| API Gateway  | Node.js 22 · Fastify · Socket.IO · Zod                  |
| AI Agents    | Python 3.11 · FastAPI · CrewAI · Hugging Face           |
| Go Gateway   | Go 1.22 · gorilla/mux · Redis pub/sub bridge            |
| Databases    | PostgreSQL 16 + pgvector · Neo4j · Redis                |
| ML           | Sentence Transformers · Few-Shot Learning · MANN · SNN  |
| DevOps       | Docker · Turborepo · GitHub Actions                     |
| Deployment   | Render (backend) · GitHub Pages (frontend)              |

## Architecture

```
Browser → GitHub Pages (Next.js static)
               ↓ HTTPS/WSS
         Render: Go Gateway (rate limiting, WS bridge)
               ↓
         Render: Node.js API (Fastify)
               ↓ HTTP
         Render: Python Orchestrator (FastAPI)
               ↓
    ┌──────────┴───────────┐
    │  7 Parallel Agents   │
    │  Sentry · Financial  │
    │  Talent · TechStack  │
    │  Sentiment · Reg.    │
    │  Competitive         │
    └──────────┬───────────┘
               ↓
    Neo4j Knowledge Graph
               ↓
    Debate Chamber (Bull/Bear/Skeptic/Synthesizer)
               ↓
    Strategic Report + Meta-Learning Update
```

## Quick Start

```bash
# Setup: Install all dependencies (Node & Python)
./setup-local.bat

# Run: Start infrastructure (Docker) and all apps
./start-local.bat
```

Open:
- **Web Dashboard**: http://localhost:3001
- **API Docs**: http://localhost:3000/docs
- **Orchestrator Docs**: http://localhost:8001/docs

## Deployment

See **[DEPLOYMENT.md](./DEPLOYMENT.md)** for full hybrid deployment guide:
- **Backend** → Render.com (Node.js + Python + Go)
- **Frontend** → GitHub Pages (Next.js static export)

## Project Structure

```
aegis/
├── apps/
│   ├── api/               # Node.js + Fastify API
│   └── web/               # Next.js 14 frontend
├── services/
│   ├── agent-orchestrator/ # Python FastAPI + all agents
│   └── go-gateway/        # Go reverse proxy + WS bridge
├── infrastructure/
│   ├── render.yaml        # Render Blueprint
│   └── k8s/               # Kubernetes manifests
├── .github/workflows/     # CI/CD pipelines
├── docker-compose.yml     # Local dev stack
└── DEPLOYMENT.md          # Full deployment guide
```

## Key Features

- **7 Specialized Agents**: Sentry, Financial Archaeologist, Talent Flow, Tech Stack, Sentiment Scout, Regulatory Radar, Competitive Cartographer
- **Adversarial Debate**: Bull vs Bear vs Skeptic → Synthesizer resolves with confidence intervals
- **Knowledge Graph**: Neo4j-powered entity relationships with Cytoscape.js visualization
- **Few-Shot Learning**: pgvector similarity search + MMR diversity selection
- **Monte Carlo Simulation**: 1000-run what-if scenario analysis
- **Real-time**: Socket.IO + Redis pub/sub live agent telemetry
- **Go Gateway**: Sub-millisecond rate limiting, WebSocket bridging, health aggregation
- **Ethical Scraping**: robots.txt compliance, rate limiting, PII scrubbing

## LLM Benchmarks

| Metric                  | Target   |
|-------------------------|----------|
| Source Attribution Rate | >95%     |
| Inter-Agent Consensus   | >80%     |
| Brier Score (confidence)| <0.2     |
| Cost per Investigation  | <$3.00   |
| End-to-End Latency      | <6 min   |

---

*Built as a demonstration of systems thinking: distributed AI, meta-learning, graph databases, and production-grade DevOps.*
