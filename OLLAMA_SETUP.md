# Ollama Local LLM Support

### Ollama Service in Docker Compose

The docker-compose.yml includes an Ollama service that provides local LLM inference:

```yaml
ollama:
  image: ollama/ollama:latest
  ports:
    - "11434:11434"
  volumes:
    - ollama_data:/root/.ollama
  entrypoint: [/bin/sh, -c]
  command: |
    ollama serve
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
  restart: unless-stopped
```

### Setting Up Ollama for Docker

#### Option 1: With Docker Compose (Recommended for local development)
```bash
# Navigate to AEGIS directory
cd /path/to/aegis/AEGIS

# Create .env file with Ollama configuration
cp .env-ollama.example .env

# Edit .env and set Ollama configuration
# Example:
export OLLAMA_API_URL="http://localhost:11434/v1/chat/completions"
export OLLAMA_MODEL="gemma4:latest"

# Stop any existing Ollama containers (if any)
docker-compose down ollama

# Start all services including Ollama
docker-compose up -d

# The Ollama service will automatically pull gemma4:latest
# You can check status with: docker-compose ps
```

#### Option 2: Separate Ollama Installation
```bash
# Install Ollama (system package manager)
# macOS: brew install ollama
# Linux: curl -fsSL https://ollama.ai/install.sh | sh
# Windows: Download from https://ollama.ai/download

# Start Ollama (background)
ollama serve &

# Pull gemma4 model (or any other model)
ollama pull gemma4:latest

# Keep Ollama running and start AEGIS
# Create .env file with Ollama configuration
# Then run: cd /path/to/aegis/AEGIS && ./deploy-docker.sh deploy
```

### Environment Variables for Ollama

In your `.env` file, set:
```bash
# Ollama API URL (defaults to localhost:11434)
OLLAMA_API_URL="http://localhost:11434/v1/chat/completions"

# Local model to use (can be any Ollama model)
OLLAMA_MODEL="gemma4:latest"

# Optional: Multiple models for fallback (comma-separated)
OLLAMA_MODELS="gemma4:latest,llama3.1:latest,codeqwen:7b"

# Remove or comment out cloud API keys to prioritize local LLM
# export OPENAI_API_KEY="sk-your-key"
# export GEMINI_API_KEY="your-key"
# export GROQ_API_KEY="your-key"
# export OPENROUTER_API_KEY="your-key"
```

### Common Ollama Models

| Model | Description | Recommended For |
|-------|-------------|----------------|
| `gemma4:latest` | Latest gemma4 model | General purpose, chat, reasoning |
| `gemma4:2b` | Smaller gemma4 variant | Resource-constrained environments |
| `llama3.1:latest` | Meta's llama 3.1 | General purpose, coding |
| `llama3.2:latest` | Latest llama 3.2 | Strong reasoning capabilities |
| `codeqwen:7b` | Code-specialized model | Programming tasks |

### Deployment with Ollama

#### Quick Start Script

Create a script for Ollama deployment:
```bash
#!/bin/bash
# deploy-with-ollama.sh

echo "🚀 Starting AEGIS with local Ollama LLM"

echo "1. Checking for Ollama installation..."
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama not found. Install from: https://ollama.ai/"
    exit 1
fi

echo "2. Pulling gemma4 model (this may take a few minutes)..."
ollama pull gemma4:latest

echo "3. Creating .env file..."
cp .env-ollama.example .env

# Edit .env file to uncomment Ollama settings and comment out cloud keys
# (Or create your own .env file)

echo "4. Starting Docker services..."
docker-compose up -d

# The deploy-docker.sh script will automatically start Ollama and pull gemma4
./deploy-docker.sh deploy

echo "✅ AEGIS deployed with local gemma4 LLM"
echo "Access your platform at: http://localhost:3001"
```

### Ollama Volume Management

The Ollama service uses a Docker volume `ollama_data` to persist models:

```bash
# View Ollama volume size
docker volume inspect aegis_ollama_data

# Remove Ollama volume (will require redownloading models)
docker volume rm aegis_ollama_data
```

### Troubleshooting Ollama in Docker

#### Ollama Service Not Starting
```bash
# Check Ollama logs
docker-compose logs ollama

# Try to start Ollama manually
ollama serve
```

#### gemma4 Model Not Available
```bash
# Check available models in Ollama container
docker-compose exec ollama ollama list

# Pull the model if not available
docker-compose exec ollama ollama pull gemma4:latest
```

#### Network Connectivity Issues
```bash
# Check if Ollama is accessible from other services
# The Ollama service is available as 'ollama' within the docker-compose network
# Agent Orchestrator can connect to: http://ollama:11434/v1/chat/completions
```

### Monitoring Ollama

#### Resource Usage
```bash
# Monitor Ollama container resources
docker stats ollama

# Check Ollama logs for model loading
ollama logs
```

#### Model Availability
```bash
# Test Ollama API endpoint
curl http://localhost:11434/api/tags

# Check if gemma4 is available
curl http://localhost:11434/api/tags | jq '.models[] | select(.name | contains("gemma4"))'
```

### Security Considerations

#### Local Ollama Security
- Ollama runs in a container with limited network access
- Model files are stored in Docker volume
- API endpoint requires authentication (Docker network isolation)

#### Production Considerations
- For production, consider using the monolithic Dockerfile
- Monitor Ollama resource usage to prevent OOM errors
- Consider setting up authentication for Ollama API

### Common Issues and Solutions

#### Issue: "Ollama is not responding"
```bash
# Restart Ollama service
docker-compose restart ollama

# Check logs
docker-compose logs ollama
```

#### Issue: gemma4 model not found
```bash
# Pull the model with retry logic
docker-compose exec ollama ollama pull gemma4:latest --timeout 300
```

#### Issue: Insufficient system resources
```bash
# Check system resources
docker stats ollama

# Monitor CPU/memory usage
watch -n 1 "docker stats ollama"
```

### Best Practices

#### For Development
1. **Use Docker Compose with Ollama service** for easy setup
2. **Pull multiple models** for fallback options
3. **Set up monitoring** for Ollama resource usage
4. **Use volume persistence** for model storage

#### For Production
1. **Use the monolithic Dockerfile** for single container deployment
2. **Configure resource limits** to prevent OOM errors
3. **Set up monitoring** and alerting
4. **Use authentication** for Ollama API access

### Summary

Ollama provides a powerful local LLM solution for AEGIS:

✅ **Zero cost** - No API fees
✅ **Fast inference** - Local processing
✅ **Full control** - Your models, your data
✅ **Offline capability** - Works without internet
✅ **Easy setup** - Docker Compose integration
✅ **Persist models** - Docker volumes store models

**Simply configure Ollama in your .env file and let AEGIS use local gemma4 instead of cloud API keys!** 🚀
