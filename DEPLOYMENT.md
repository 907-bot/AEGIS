# AEGIS — Hybrid Deployment Guide
## Backend → Render | Frontend → GitHub Pages

---

## Architecture Overview

```
[GitHub Pages]          [Render.com]
  Next.js (Static)  →   Go Gateway (8080)
                     →   Node.js API (3000)
                     →   Python Orchestrator (8001)
                     →   PostgreSQL (managed)
                     →   Redis (managed)

                     [External / Self-hosted]
                     →   Neo4j AuraDB (free tier)
```

---

## Part 1 — Backend on Render

### Step 1: Prerequisites
- Render account at render.com (free tier works)
- GitHub repo with this codebase pushed
- OpenAI API key + Anthropic API key

### Step 2: Setup Neo4j AuraDB (Free)
1. Go to https://neo4j.com/cloud/aura-free/
2. Create a free AuraDB instance
3. Copy the connection string → you'll need:
   - `NEO4J_URL=neo4j+s://xxxx.databases.neo4j.io`
   - `NEO4J_USER=neo4j`
   - `NEO4J_PASSWORD=<generated>`

### Step 3: Deploy via render.yaml (Blueprint)

**Option A — Render Blueprint (Recommended)**
```bash
# In your repo root, the render.yaml is already configured.
# Just go to: https://dashboard.render.com/select-repo
# → Select your GitHub repo
# → Render auto-detects render.yaml
# → Click "Apply" → all 3 services + DB + Redis deploy automatically
```

**Option B — Manual Service Creation**

#### 3a. Create PostgreSQL
```
Render Dashboard → New → PostgreSQL
  Name: aegis-postgres
  Database: aegis
  User: aegis_user
  Plan: Free
→ Save the "Internal Connection String"
```

#### 3b. Create Redis
```
Render Dashboard → New → Redis
  Name: aegis-redis
  Plan: Free (25MB)
→ Save the "Internal Redis URL"
```

#### 3c. Deploy Node.js API
```
Render Dashboard → New → Web Service
  Name:          aegis-api
  Runtime:       Node
  Root Dir:      apps/api
  Build:         npm install && npm run build
  Start:         node dist/index.js
  Health Check:  /health/live
  Plan:          Free (or Starter)

Environment Variables:
  NODE_ENV           = production
  PORT               = 3000
  DATABASE_URL       = <postgres internal URL>
  REDIS_URL          = <redis internal URL>
  NEO4J_URL          = neo4j+s://xxxx.databases.neo4j.io
  NEO4J_USER         = neo4j
  NEO4J_PASSWORD     = <your neo4j password>
  OPENAI_API_KEY     = sk-...
  ANTHROPIC_API_KEY  = sk-ant-...
  CORS_ORIGIN        = https://<your-github-username>.github.io
```

#### 3d. Deploy Python Orchestrator
```
Render Dashboard → New → Web Service
  Name:     aegis-orchestrator
  Runtime:  Python 3
  Root Dir: services/agent-orchestrator
  Build:    pip install -r requirements.txt && playwright install chromium --with-deps
  Start:    uvicorn main:app --host 0.0.0.0 --port 8001 --workers 2
  Plan:     Starter (Free won't run Playwright well)

Environment Variables:
  DATABASE_URL       = <postgres internal URL>
  REDIS_URL          = <redis internal URL>
  NEO4J_URL          = neo4j+s://xxxx.databases.neo4j.io
  NEO4J_USER         = neo4j
  NEO4J_PASSWORD     = <your neo4j password>
  OPENAI_API_KEY     = sk-...
  ANTHROPIC_API_KEY  = sk-ant-...
  SCRAPING_CONCURRENCY = 2
```

#### 3e. Deploy Go Gateway (optional but recommended)
```
Render Dashboard → New → Web Service
  Name:     aegis-go-gateway
  Runtime:  Go
  Root Dir: services/go-gateway
  Build:    go build -o gateway ./cmd/server
  Start:    ./gateway
  Plan:     Free

Environment Variables:
  GATEWAY_PORT    = 8080
  API_URL         = https://aegis-api.onrender.com
  ORCHESTRATOR_URL= https://aegis-orchestrator.onrender.com
  REDIS_URL       = <redis internal URL>
```

### Step 4: Run Database Migrations
After services deploy, open the Render Shell for `aegis-api`:
```bash
# In Render Dashboard → aegis-api → Shell
psql $DATABASE_URL < src/db/schema.sql
```

Or use the one-shot migration job:
```bash
node dist/db/migrate.js
```

### Step 5: Note Your Service URLs
After all services are deployed, copy:
```
API URL:          https://aegis-api.onrender.com
Orchestrator URL: https://aegis-orchestrator.onrender.com
Gateway URL:      https://aegis-go-gateway.onrender.com
```

---

## Part 2 — Frontend on GitHub Pages

### Step 1: GitHub Repository Settings
```
Your Repo → Settings → Pages
  Source: GitHub Actions
  (leave branch blank — the workflow handles it)
```

### Step 2: Add GitHub Secrets
```
Your Repo → Settings → Secrets → Actions → New Secret

RENDER_API_URL   = https://aegis-api.onrender.com
RENDER_WS_URL    = wss://aegis-api.onrender.com
```

Also add for auto-deploy triggers:
```
RENDER_DEPLOY_HOOK_API          = https://api.render.com/deploy/srv-xxx?key=yyy
RENDER_DEPLOY_HOOK_ORCHESTRATOR = https://api.render.com/deploy/srv-xxx?key=yyy
RENDER_DEPLOY_HOOK_GATEWAY      = https://api.render.com/deploy/srv-xxx?key=yyy
```
(Get deploy hooks from: Render Dashboard → each service → Settings → Deploy Hooks)

### Step 3: Update next.config.js for your repo name
If your repo is `github.com/username/aegis`, update `apps/web/next.config.js`:
```js
const nextConfig = {
  output: 'export',
  basePath: '/aegis',          // ← add your repo name
  trailingSlash: true,
  images: { unoptimized: true },
  ...
};
```

### Step 4: Deploy
```bash
git add .
git commit -m "feat: deploy AEGIS"
git push origin main
```

GitHub Actions will:
1. Build the Next.js static export
2. Deploy to `https://<username>.github.io/aegis`

Check progress: `Your Repo → Actions → Deploy Frontend → GitHub Pages`

---

## Part 3 — CORS Configuration

After deploying frontend, update `CORS_ORIGIN` on the **aegis-api** Render service:
```
CORS_ORIGIN = https://<username>.github.io
```

For Socket.IO to work across domains, also ensure Render service URLs are HTTPS.

---

## Part 4 — Local Development

### One-command start
```bash
# Clone and setup
git clone https://github.com/<you>/aegis
cd aegis
cp .env.example .env
# Fill in your API keys in .env

# Start everything (backend runs locally; Docker only for infra)
./start-local.bat

# Services will be at:
#   Frontend:      http://localhost:3001
#   API:           http://localhost:3000
#   Orchestrator:  http://localhost:8001
#   Go Gateway:    http://localhost:8080
#   Neo4j Browser: http://localhost:7474
#   Temporal UI:   http://localhost:8080
```

### Run services individually
```bash
# API
cd apps/api && npm install && npm run dev

# Frontend
cd apps/web && npm install && npm run dev

# Python orchestrator
cd services/agent-orchestrator
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload --port 8001

# Go Gateway
cd services/go-gateway
go run ./cmd/server
```

---

## Part 5 — Environment Summary

| Variable                | Where to Set          | Value                              |
|-------------------------|-----------------------|------------------------------------|
| `DATABASE_URL`          | Render (API + Orch)   | From Render PostgreSQL service     |
| `REDIS_URL`             | Render (all)          | From Render Redis service          |
| `NEO4J_URL`             | Render (API + Orch)   | From Neo4j AuraDB                  |
| `OPENAI_API_KEY`        | Render (API + Orch)   | Your OpenAI key                    |
| `ANTHROPIC_API_KEY`     | Render (API + Orch)   | Your Anthropic key                 |
| `CORS_ORIGIN`           | Render (API)          | `https://<user>.github.io`         |
| `NEXT_PUBLIC_API_URL`   | GitHub Secret         | `https://aegis-api.onrender.com`   |
| `NEXT_PUBLIC_WS_URL`    | GitHub Secret         | `wss://aegis-api.onrender.com`     |

---

## Part 6 — Cost Breakdown (Free Tier)

| Service                 | Provider          | Cost/Month    |
|-------------------------|-------------------|---------------|
| Frontend                | GitHub Pages      | **FREE**      |
| Node.js API             | Render Free       | **FREE**      |
| Python Orchestrator     | Render Starter    | ~$7           |
| Go Gateway              | Render Free       | **FREE**      |
| PostgreSQL              | Render Free       | **FREE**      |
| Redis                   | Render Free       | **FREE**      |
| Neo4j                   | AuraDB Free       | **FREE**      |
| OpenAI / Anthropic      | Pay-per-use       | ~$2-5/report  |
| **Total**               |                   | **~$7/month** |

> **Note:** Render free tier spins down after 15 min inactivity.
> For always-on, upgrade API + Orchestrator to Starter ($7/service/month each).

---

## Troubleshooting

### Frontend can't reach API
```
✅ Check CORS_ORIGIN matches your GitHub Pages URL exactly
✅ Verify NEXT_PUBLIC_API_URL secret is set correctly
✅ Check Render service is not sleeping (free tier)
```

### Playwright fails on Render
```bash
# In Python service build command, add:
playwright install chromium --with-deps
# Use Starter plan (not Free) — Free doesn't support Playwright
```

### WebSocket connections dropping
```
✅ Use wss:// (not ws://) for production
✅ Enable sticky sessions in Render if using multiple workers
✅ Socket.IO falls back to polling automatically
```

### Neo4j connection refused
```
✅ Use neo4j+s:// (TLS) for AuraDB, not bolt://
✅ Allow ~30s for AuraDB to wake up if it's been idle
```
