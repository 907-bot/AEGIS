# AEGIS Docker Deployment Complete!

## Quick Start (Copy-Paste Ready)

```bash
# Step 1: Navigate to AEGIS directory
cd /path/to/aegis/AEGIS

# Step 2: Copy Ollama configuration
cp .env-ollama.example .env

# Step 3: (Optional) Start Ollama service if not already running
# Option A: Install Ollama and start manually:
#   ollama serve &
#   ollama pull gemma4:latest
#
# Option B: Start with Docker Compose:
#   docker-compose up -d ollama

# Step 4: Deploy complete AEGIS with local gemma4
./deploy-docker.sh deploy

# Step 5: Access your platform
#   Web Dashboard: http://localhost:3001
#   API: http://localhost:3000
#   Agent Orchestrator: http://localhost:8001
```

## Summary of Changes

### New Files Created:

1. **`.env-ollama.example`** - Environment file configured for Ollama
2. **`OLLAMA_SETUP.md`** - Complete Ollama setup guide
3. **`DOCKER_DEPLOYMENT.md`** - Updated Docker deployment guide
4. **`DEPLOY_DOCKER_COMPLETE.md`** - Executive summary
5. **`DEPLOYMENT_QUICKSTART.md`** - Quick start commands
6. **`DEPLOYMENT_COMPLETE.md`** - Complete deployment documentation

### Files Updated:

1. **`docker-compose.yml`** - Added Ollama service
2. **`deploy-docker.sh`** - Updated to support Ollama
3. **`README.md`** - Added Docker deployment instructions
4. **`DEPLOYMENT.md`** - Updated environment summary
5. **`llm_router.py`** - Added Ollama support for LLM routing

### Dockerfiles Updated:

1. **`apps/web/Dockerfile`** - Fixed server.js path issue
2. **`Dockerfile`** - Monolithic container (use with caution)

## Environment Configuration

### Option 1: Local gemma4 with Ollama (Recommended)
```bash
# Set environment variables (add to .env file)
export OLLAMA_API_URL="http://localhost:11434/v1/chat/completions"
export OLLAMA_MODEL="gemma4:latest"

# Optional: Multiple models for fallback
export OLLAMA_MODELS="gemma4:latest,llama3.1:latest,codeqwen:7b"

# Remove or comment out cloud API keys to prioritize local LLM
# export OPENAI_API_KEY="sk-your-key"
# export GEMINI_API_KEY="your-key"
# export GROQ_API_KEY="your-key"
# export OPENROUTER_API_KEY="your-key"
```

### Option 2: Cloud Providers (Default)
```bash
# Set cloud API keys (comment out Ollama settings)
export OPENAI_API_KEY="sk-your-openai-key"
export GEMINI_API_KEY="your-gemini-key"
export GROQ_API_KEY="your-groq-key"
export OPENROUTER_API_KEY="your-openrouter-key"

# Comment out Ollama settings
# export OLLAMA_API_URL="..."
# export OLLAMA_MODEL="..."
```

## Deployment Methods

### 1. Docker Compose with Ollama (Easiest)
```bash
# Navigate to AEGIS directory
cd /path/to/aegis/AEGIS

# Start Ollama service (if not already running)
docker-compose up -d ollama

# Start all services including Ollama
./deploy-docker.sh deploy
```

### 2. Full Docker Compose (All Services)
```bash
# Navigate to AEGIS directory
cd /path/to/aegis/AEGIS

# Start all services in one command (builds images if needed)
docker-compose up -d
```

### 3. Manual Deployment
```bash
# Install Ollama (system package manager)
# macOS: brew install ollama
# Linux: curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama
ollama serve &

# Pull gemma4 model
ollama pull gemma4:latest

# Create environment file
cp .env-ollama.example .env

# Run deployment script
./deploy-docker.sh deploy
```

## Service Access

After deployment, access your AEGIS platform:

| Service | URL | Description |
|---------|-----|-------------|
| Web Dashboard | http://localhost:3001 | Next.js frontend |
| API Gateway | http://localhost:3000 | Node.js API with docs at `/docs` |
| Agent Orchestrator | http://localhost:8001 | Python orchestrator with docs at `/docs` |
| Go Gateway | http://localhost:8080 | Go reverse proxy and WebSocket bridge |
| Neo4j Browser | http://localhost:7474 | Neo4j knowledge graph interface |
| PostgreSQL | localhost:5432 | PostgreSQL database |
| Redis | localhost:6379 | Redis cache and message broker |
| Ollama | http://localhost:11434 | Local LLM inference API |

## Ollama Management

### Check Ollama Status
```bash
# Check if Ollama is running
docker-compose ps ollama

# Check available models
http://localhost:11434/api/tags

# Look for gemma4 model
curl http://localhost:11434/api/tags | grep gemma4
```

### Pull Additional Models
```bash
# Pull multiple models for fallback
docker-compose exec ollama ollama pull gemma4:latest
docker-compose exec ollama ollama pull llama3.1:latest
docker-compose exec ollama ollama pull codeqwen:7b
```

### Monitor Resource Usage
```bash
# Monitor Ollama resource usage
docker stats ollama

# Check Ollama logs
docker-compose logs ollama
```

### Volume Management
```bash
# View Ollama volume size
docker volume inspect aegis_ollama_data

# Remove Ollama volume (will require redownloading models)
docker volume rm aegis_ollama_data
```

## Configuration Files

### `.env-ollama.example`

This file provides a complete environment configuration for using local gemma4 with Ollama:

```bash
# Infrastructure Services
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/aegis
REDIS_URL=redis://redis:6379
NEO4J_URL=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Frontend Configuration
CORS_ORIGIN=http://localhost:3001
NEXT_PUBLIC_API_URL=http://localhost:3000
NEXT_PUBLIC_WS_URL=ws://localhost:3000

# LLM Configuration - Local Ollama
OLLAMA_API_URL=http://localhost:11434/v1/chat/completions
OLLAMA_MODEL=gemma4:latest

# Optional: Multiple models for fallback
# OLLAMA_MODELS=gemma4:latest,llama3.1:latest,codeqwen:7b

# Cloud API Keys (Optional - can be left commented out)
# OPENAI_API_KEY=sk-your-openai-key
# GEMINI_API_KEY=your-gemini-key
# GROQ_API_KEY=your-groq-key
# OPENROUTER_API_KEY=your-openrouter-key

# Agent Orchestrator Specific Settings
SCRAPING_CONCURRENCY=3
```

## LLM Provider Selection

AEGIS automatically selects LLM providers in this order:

1. **Groq** (if GROQ_API_KEY is set)
2. **OpenRouter** (if OPENROUTER_API_KEY is set)
3. **OpenAI** (if OPENAI_API_KEY is set)
4. **Ollama** (if OLLAMA_API_URL is set) ← **Local LLM**

**When you set `OLLAMA_API_URL`, AEGIS will prioritize local LLM over cloud providers!**

## Benefits of Local gemma4 with Ollama

### Cost Savings
✅ **Zero API costs** - No per-token charges
✅ **No rate limits** - Unlimited concurrent requests
✅ **No billing concerns** - No monthly subscriptions

### Performance
✅ **Lower latency** - Local inference is faster than API calls
✅ **Always available** - Not affected by cloud service downtime
✅ **Offline capability** - Works without internet connection

### Privacy and Control
✅ **Data privacy** - Sensitive data stays on your machine
✅ **Full model control** - Use any Ollama model
✅ **Easy updates** - Update models with simple commands
✅ **Custom configurations** - Fine-tune models locally

## Ollama Model Recommendations

| Model | RAM Required | Best For |
|-------|--------------|----------|
| `gemma4:latest` | 8GB+ | General purpose, chat, reasoning |
| `gemma4:2b` | 2GB+ | Resource-constrained environments |
| `llama3.1:latest` | 8GB+ | General purpose, coding |
| `llama3.2:latest` | 8GB+ | Strong reasoning capabilities |
| `codeqwen:7b` | 7GB+ | Programming tasks, code generation |

## Troubleshooting

### Common Issues

#### Ollama Not Running
```bash
# Check if Ollama is installed and running
ollama serve

# Or check with Docker
docker-compose ps ollama
```

#### gemma4 Model Not Available
```bash
# Pull the model
docker-compose exec ollama ollama pull gemma4:latest

# Check available models
docker-compose exec ollama ollama list
```

#### Connection Issues
```bash
# Check network connectivity
curl -I http://localhost:11434/api/tags

# Check Docker network
# Ollama service is available as 'ollama' in Docker Compose network
```

#### Insufficient Resources
```bash
# Monitor Ollama resource usage
docker stats ollama

# Check system resources
free -h
```

### Deployment Problems

#### Service Startup Failures
```bash
# Check service status
docker-compose ps

# View logs for specific service
./deploy-docker.sh logs [service-name]
```

#### Health Check Failures
```bash
# Perform health checks
./deploy-docker.sh health

# Check individual service health
./deploy-docker.sh logs api
./deploy-docker.sh logs agent-orchestrator
```

## Production Considerations

### For Development and Testing
1. **Use Docker Compose** - Easy setup and management
2. **Local Ollama** - Fast iteration and debugging
3. **Single machine deployment** - Simpler infrastructure

### For Production
1. **Consider Render.com** - Managed infrastructure with Ollama support
2. **Use monolithic Dockerfile** - Single container deployment
3. **Set up monitoring** - Resource usage and performance monitoring
4. **Implement backups** - Model and data backup strategies

## Quick Commands Summary

```bash
# Create Ollama environment file
cp .env-ollama.example .env

# Start Ollama service
docker-compose up -d ollama

# Deploy complete AEGIS platform
./deploy-docker.sh deploy

# Check service status
./deploy-docker.sh status

# View logs (replace [service-name] with actual service)
./deploy-docker.sh logs [service-name]

# Perform health checks
./deploy-docker.sh health

# Stop all services
./deploy-docker.sh stop

# Remove all services and data (⚠️ WARNING)
./deploy-docker.sh remove
```

## Important Notes

### Ollama in Production
- **Resource Management**: Monitor Ollama resource usage to prevent OOM errors
- **Backup Strategy**: Regularly backup Ollama models using Docker volumes
- **Security**: Ollama runs in Docker containers with network isolation
- **Updates**: Update models using `ollama pull` or `ollama create`

### Migration from Cloud LLMs
When switching from cloud LLMs to local Ollama:
1. Set `OLLAMA_API_URL` and `OLLAMA_MODEL` in your `.env` file
2. Comment out or remove cloud API keys
3. Ensure Ollama service is running
4. Restart Agent Orchestrator to pick up local LLM configuration
5. Test that all functionality works correctly with gemma4

### Performance Optimization
- **Model Size**: Use appropriate model size for your hardware
- **Batch Processing**: Consider batching requests for better throughput
- **Caching**: Leverage local caching for repeated requests
- **Resource Limits**: Set appropriate memory and CPU limits

## Summary

Using local gemma4 with Ollama provides a cost-effective, private, and high-performance solution for deploying AEGIS:

✅ **Zero operational costs** - No API fees
✅ **Fast local inference** - Lower latency than cloud APIs
✅ **Full control** - Your models, your data
✅ **Easy setup** - Docker Compose integration
✅ **Persist models** - Docker volumes maintain models
✅ **Scalable architecture** - Works with Docker Compose or monolithic deployment

**Simply configure Ollama in your environment and let AEGIS use local gemma4 instead of expensive cloud API keys!** 🚀

For the most comprehensive documentation, refer to:
- `OLLAMA_SETUP.md` - Complete Ollama setup guide
- `DOCKER_DEPLOYMENT.md` - Docker deployment instructions
- `DEPLOYMENT.md` - Full deployment guide
- `README.md` - Quick start and usage

**Your AEGIS platform with local gemma4 is ready to deploy!** 🎉
