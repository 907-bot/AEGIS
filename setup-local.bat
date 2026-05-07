@echo off
echo ──────────────────────────────────────────────────────────
echo 🚀 AEGIS — Local Environment Setup
echo ──────────────────────────────────────────────────────────

echo [1/3] Installing Root and Workspace Dependencies...
npm install

echo [2/3] Setting up Agent Orchestrator (Python)...
cd services/agent-orchestrator
python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
cd ../..

echo [3/3] Initialising Environment...
if not exist .env (
    copy .env.example .env
    echo ⚠️ Created .env from .env.example. Please fill in your API keys.
)

echo ──────────────────────────────────────────────────────────
echo ✅ Setup Complete! 
echo 1. Ensure Docker is running for infrastructure (Postgres, Redis, Neo4j).
echo 2. Run 'npm run infra' to start databases.
echo 3. Run 'npm run dev' to start application services.
echo ──────────────────────────────────────────────────────────
pause
