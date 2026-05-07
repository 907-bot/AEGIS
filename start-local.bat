@echo off
echo ──────────────────────────────────────────────────────────
echo 🚀 AEGIS — Starting Local Services
echo ──────────────────────────────────────────────────────────

echo [1/4] Starting Infrastructure (Docker)...
docker-compose up -d postgres redis neo4j

echo [2/4] Starting API Gateway (Node)...
start "AEGIS API" cmd /c "npm run dev --filter=@aegis/api"

echo [3/4] Starting Frontend (Next.js)...
start "AEGIS Web" cmd /c "npm run dev --filter=@aegis/web"

echo [4/4] Starting Agent Orchestrator (Python)...
start "AEGIS Orchestrator" cmd /c "cd services/agent-orchestrator && venv\Scripts\activate && python main.py"

echo ──────────────────────────────────────────────────────────
echo ✅ All services are starting in separate windows.
echo - API: http://localhost:3000
echo - Web: http://localhost:3001
echo - Orchestrator: http://localhost:8001
echo ──────────────────────────────────────────────────────────
pause
