# AEGIS Docker Deployment Guide

This guide explains how to deploy the complete AEGIS platform using Docker containers. 
For this microservices architecture, we recommend using **<co>docker-compose</co: 4:[0]>** for production deployments, which provides better <co>service isolation</co: 4:[0]>, <co>scalability</co: 4:[0]>, and <co>management</co: 4:[0]>.

## Overview

The AEGIS platform consists of <co>6 containers</co: 4:[0]>:
- **<co>PostgreSQL</co: 4:[0]>**: <co>Database with vector support</co: 4:[0]> <co>(5432)</co: 4:[0]>
- **<co>Redis</co: 4:[0]>**: <co>Message broker and caching</co: 4:[0]> <co>(6379)</co: 4:[0]>
- **<co>Neo4j</co: 4:[0]>**: <co>Knowledge graph database</co: 4:[0]> <co>(7474, 7687)</co: 4:[0]>
- **<co>api</co: 4:[0]>**: <co>Node.js API Gateway (Fastify)</co: 4:[0]> <co>(3000)</co: 4:[0]>
- **<co>web</co: 4:[0]>**: <co>Next.js Frontend</co: 4:[0]> <co>(3001)</co: 4:[0]>
- **<co>agent-orchestrator</co: 4:[0]>**: <co>Python Agent Orchestrator (FastAPI)</co: 4:[0]> <co>(8001)</co: 4:[0]>
- **<co>go-gateway</co: 4:[0]>**: <co>Go reverse proxy + WebSocket bridge</co: 4:[0]> <co>(8080)</co: 4:[0]>

## Prerequisites

- Docker installed on your system
- At least 4GB RAM (for databases and services)
- 20GB disk space (for PostgreSQL data and images)

## Quick Start with Docker Compose (Recommended)

### 1. Start All Services

```bash
# Navigate to the AEGIS directory
cd /path/to/aegis/AEGIS

# Start all services in one command (builds images if needed)
docker-compose up -d

# Check status
docker-compose ps
```

### 2. Wait for Services to Initialize

```bash
# Wait for databases (especially Neo4j) to fully start (60-90 seconds)
sleep 90

# Check service status
docker-compose ps
```

### 3. Check Database Connectivity

```bash
# Test database connectivity
docker-compose exec postgres pg_isready -U postgres
docker-compose exec redis redis-cli ping
docker-compose exec neo4j wget --quiet --tries=1 --spider http://localhost:7474
```

### 4. Initialize Database Schema

```bash
# Run database migration
docker-compose exec api psql "$DATABASE_URL" -f src/db/schema.sql
```

### 2. Wait for Databases to Initialize

```bash
# Wait for services to be ready (5-10 seconds)
sleep 10

# Check database connectivity
# PostgreSQL
docker exec aegis_postgres pg_isready -U postgres

# Redis
docker exec aegis_redis redis-cli ping

# Neo4j (wait longer, Neo4j takes ~30 seconds to start)
sleep 30
docker exec aegis_neo4j wget --quiet --tries=1 --spider http://localhost:7474
```

### 3. Initialize Database Schema

```bash
# Create a migration script
cat > /tmp/migrate.sh << 'EOF'
#!/bin/bash
# Wait for API service to be available
docker-compose up -d api
sleep 15

# Run schema migration
docker-compose exec api psql "$DATABASE_URL" -f src/db/schema.sql
echo "Database migration completed!"
EOF

chmod +x /tmp/migrate.sh
/tmp/migrate.sh
```

### 4. Start Application Services

```bash
# Start all application services (can start in any order)
docker-compose up -d api web agent-orchestrator go-gateway

# Check status
docker-compose ps
```

### 5. Access the Services

Once all services are running, access:

- **Web Dashboard**: http://localhost:3001
- **API Gateway**: http://localhost:3000 (API docs: http://localhost:3000/docs)
- **Agent Orchestrator**: http://localhost:8001 (API docs: http://localhost:8001/docs)
- **Go Gateway**: http://localhost:8080
- **Neo4j Browser**: http://localhost:7474

## Building Individual Services

Each service has its own Dockerfile. Build them individually if needed:

```bash
# Build and run API Gateway
docker-compose build api
docker-compose up -d api

# Build and run Frontend
docker-compose build web
docker-compose up -d web

# Build and run Agent Orchestrator
docker-compose build agent-orchestrator
docker-compose up -d agent-orchestrator

# Build and run Go Gateway
docker-compose build go-gateway
docker-compose up -d go-gateway
```

## Docker Compose Commands

### Common Operations

```bash
# View container status
docker-compose ps

# View logs (follow)
docker-compose logs -f [service-name]

# View logs for all services
docker-compose logs -f

# Restart a service
docker-compose restart api

# Stop all services
docker-compose down

# Remove all volumes and restart (⚠️ WARNING: Deletes all data)
docker-compose down -v
```

### Service Health Checks

```bash
# Check API health
docker-compose exec api curl -f http://localhost:3000/health/live

# Check Agent Orchestrator health
docker-compose exec agent-orchestrator curl -f http://localhost:8001/health

# Check Go Gateway health
docker-compose exec go-gateway curl -f http://localhost:8080/health
```

## Environment Variables

Required environment variables for services:

| Service | Variable | Default | Description |
|---------|----------|---------|-------------|
| api | <co>NODE_ENV</co: 4:[0]> | <co>development</co: 4:[0]> | <co>Node environment</co: 4:[0]> |
| api | <co>DATABASE_URL</co: 4:[0]> | <co>postgresql://postgres:postgres@postgres:5432/aegis</co: 4:[0]> | <co>PostgreSQL connection</co: 4:[0]> |
| api | <co>REDIS_URL</co: 4:[0]> | <co>redis://redis:6379</co: 4:[0]> | <co>Redis connection</co: 4:[0]> |
| api | <co>NEO4J_URL</co: 4:[0]> | <co>bolt://neo4j:7687</co: 4:[0]> | <co>Neo4j connection</co: 4:[0]> |
| api | <co>NEO4J_USER</co: 4:[0]> | <co>neo4j</co: 4:[0]> | <co>Neo4j username</co: 4:[0]> |
| api | <co>NEO4J_PASSWORD</co: 4:[0]> | <co>password</co: 4:[0]> | <co>Neo4j password</co: 4:[0]> |
| agent-orchestrator | <co>REDIS_URL</co: 4:[0]> | <co>redis://redis:6379</co: 4:[0]> | <co>Redis connection</co: 4:[0]> |
| agent-orchestrator | <co>NEO4J_URL</co: 4:[0]> | <co>bolt://neo4j:7687</co: 4:[0]> | <co>Neo4j connection</co: 4:[0]> |
| agent-orchestrator | <co>DATABASE_URL</co: 4:[0]> | <co>postgresql://postgres:postgres@postgres:5432/aegis</co: 4:[0]> | <co>PostgreSQL connection</co: 4:[0]> |
| web | <co>NEXT_PUBLIC_API_URL</co: 4:[0]> | <co>http://localhost:3000</co: 4:[0]> | <co>Frontend API URL</co: 4:[0]> |
| web | <co>NEXT_PUBLIC_WS_URL</co: 4:[0]> | <co>ws://localhost:3000</co: 4:[0]> | <co>Frontend WebSocket URL</co: 4:[0]> |
| go-gateway | <co>GATEWAY_PORT</co: 4:[0]> | <co>8080</co: 4:[0]> | <co>Gateway port</co: 4:[0]> |
| go-gateway | <co>API_URL</co: 4:[0]> | <co>http://api:3000</co: 4:[0]> | <co>API Gateway URL</co: 4:[0]> |
| go-gateway | <co>ORCHESTRATOR_URL</co: 4:[0]> | <co>http://agent-orchestrator:8001</co: 4:[0]> | <co>Orchestrator URL</co: 4:[0]> |

## Volume Management

Docker Compose uses named volumes for persistent data:

```bash
# List volumes
docker volume ls

# View volume sizes (may require docker-compose >= 2.0)
docker volume inspect aegis_postgres_data
docker volume inspect aegis_redis_data
docker volume inspect aegis_neo4j_data

# Remove volumes (⚠️ WARNING: Deletes all data)
docker volume rm aegis_postgres_data aegis_redis_data aegis_neo4j_data

# Recreate with data preservation (dump and restore needed for PostgreSQL)
```

## Service Logs and Monitoring

### View Application Logs

```bash
# API Gateway logs
docker-compose logs -f api

# Agent Orchestrator logs
docker-compose logs -f agent-orchestrator

# Frontend logs
docker-compose logs -f web

# All logs combined
docker-compose logs -f
```

### Container Inspection

```bash
# View container configuration
docker-compose config

# Execute commands in container (e.g., for debugging)
docker-compose exec api sh

# View running processes
docker-compose exec api ps aux
```

## Migration from Local Development

If you're currently using local development (`./setup-local.bat` + `./start-local.bat`), migrate to Docker:

### 1. Stop Local Services

```bash
# Stop local services (Windows/WSL2)
docker-compose down

# On Unix systems
./stop-local-services.sh
```

### 2. Setup Docker Environment

```bash
# Clone and setup
cd /path/to/aegis

# Create .env file from example
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️ Please edit .env and add your API keys"
fi

# Start infrastructure and services
docker-compose up -d
```

## Production Deployment (Render.com)

For production, deploy to <co>Render.com</co: 8:[0]> using the <co>blueprint approach</co: 8:[0]>:

1. Go to <co>https://dashboard.render.com/select-repo</co: 8:[0]>
2. Select your GitHub repository
3. Render auto-detects <co>`infrastructure/render.yaml</co: 8:[0]>`
4. All services deploy automatically with managed databases

See <co>`DEPLOYMENT.md</co: 8:[0]>` for detailed production setup.

## Troubleshooting

### Common Issues

1. **Database connection refused**
   ```bash
   # Check if services are running
docker-compose ps

   # Wait for Neo4j to start (it can take 30+ seconds)
sleep 35

   # Test connections
docker-compose exec postgres pg_isready -U postgres
docker-compose exec redis redis-cli ping
docker-compose exec neo4j wget --quiet --tries=1 --spider http://localhost:7474
   ```

2. **Port conflicts**
   ```bash
   # Check what's running on common ports
lsof -i :3000 -i :3001 -i :8001 -i :8080

   # Alternative for macOS
netstat -an | grep -E ':(3000|3001|8001|8080)'
   ```

3. **Memory issues**
   ```bash
   # Monitor resource usage
docker stats

   # Increase memory limits
docker-compose up -d --scale api=1 --scale web=1 --scale agent-orchestrator=1 --scale go-gateway=1
   ```

4. **Service startup order**
   ```bash
   # Ensure proper startup order with depends_on
docker-compose up -d postgres redis neo4j

   # Start dependent services after databases are ready
sleep 30
docker-compose up -d api agent-orchestrator web go-gateway
   ```

### Get Help

- Container logs: `docker-compose logs -f [service-name]`
- Network issues: Check service names and ports
- Resource limits: Monitor with `docker stats`

## Benefits of Docker Compose

1. **<co>Service Isolation</co: 4:[0]>**: Each service runs independently
2. **<co>Scalability</co: 4:[0]>**: Can scale services individually
3. **<co>Manageability</co: 4:[0]>**: Easy to monitor, log, and restart services
4. **<co>Consistency</co: 4:[0]>**: Same environment in development and production
5. **<co>Portability</co: 4:[0]>**: Works anywhere Docker runs
6. **<co>Health Checks</co: 4:[0]>**: Built-in health monitoring
7. **<co>Version Control</co: 4:[0]>**: Infrastructure as code in docker-compose.yml

## Next Steps

1. Set up environment variables and API keys
2. Test database migration
3. Verify all services are running
4. Configure production monitoring
5. Set up backups
6. Optimize performance if needed

**Recommendation**: For production use, start with docker-compose and consider moving to <co>Render.com</co: 8:[0]> or Kubernetes for larger deployments.
