# Dockerfile
# Monolithic AEGIS container that combines all services into a single container
# This provides a simple deployment option with one container running all services
# For production use, consider using docker-compose with separate services instead

FROM ubuntu:22.04

# Install essential system dependencies
RUN apt-get update && apt-get install -y \
    curl wget git python3 python3-pip python3-venv python3-dev \
    build-essential nodejs npm \
    postgresql-client redis-tools \
    gnupg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest

# Install Go 1.22
RUN wget https://go.dev/dl/go1.22.2.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.22.2.linux-amd64.tar.gz && \
    rm go1.22.2.linux-amd64.tar.gz
ENV PATH=/usr/local/go/bin:$PATH

# Install Neo4j
RUN wget -qO- https://debian.neo4j.org/neptune-release-5.x.gpg | apt-key add - \
    && echo "deb https://debian.neo4j.org/repo/ stable/" > /etc/apt/sources.list.d/neo4j.list \
    && apt-get update && apt-get install -y neo4j \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies for Agent Orchestrator
RUN python3 -m venv venv
COPY services/agent-orchestrator/requirements.txt ./
RUN ./venv/bin/pip install --no-cache-dir -r requirements.txt
RUN ./venv/bin/playwright install chromium

# Install Go dependencies for Go Gateway
WORKDIR /app/services/go-gateway
COPY services/go-gateway/go.mod services/go-gateway/go.sum ./
RUN go mod download
WORKDIR /app

# Install Node.js dependencies for API and Web services
COPY package*.json ./
RUN npm install

# Copy all source code
COPY apps/api ./apps/api
COPY apps/web ./apps/web
COPY services/agent-orchestrator ./services/agent-orchestrator
COPY services/go-gateway ./services/go-gateway

# Install additional Python packages
RUN ./venv/bin/pip install psycopg2-binary redis requests

# Database initialization script
COPY apps/api/src/db/schema.sql ./src/db/schema.sql

# Create necessary directories for data persistence
RUN mkdir -p /var/lib/postgresql/data /data/redis /var/lib/neo4j
RUN chmod -R 777 /var/lib/postgresql/data /data/redis /var/lib/neo4j

# Set environment variables
ENV PORT=3000
ENV PYTHON_ENV=development
ENV REDIS_URL=redis://localhost:6379
ENV DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aegis
ENV NEO4J_URL=bolt://localhost:7687
ENV NEO4J_USER=neo4j
ENV NEO4J_PASSWORD=password
ENV NEXT_PUBLIC_API_URL=http://localhost:3000
ENV NEXT_PUBLIC_WS_URL=ws://localhost:3000
ENV OPENAI_API_KEY=sk-your-key-here
ENV GEMINI_API_KEY=your-key-here
ENV SCRAPING_CONCURRENCY=3
ENV GATEWAY_PORT=8080

# Initialize databases on container startup
RUN cat > /app/init-databases.sh << 'EOF'
#!/bin/bash
# Set error handling to prevent script from exiting on non-zero commands
set -e

# Wait for databases to be ready
MAX_RETRIES=30
RETRY_COUNT=0

echo "Waiting for PostgreSQL..."
until docker-compose exec postgres pg_isready -U postgres || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

echo "Waiting for Redis..."
RETRY_COUNT=0
until docker-compose exec redis redis-cli ping || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

echo "Waiting for Neo4j..."
RETRY_COUNT=0
until docker-compose exec neo4j wget --quiet --tries=1 --spider http://localhost:7474 || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

# Initialize database schema
if [ -f "/app/src/db/schema.sql" ]; then
    echo "Running database migration..."
    docker-compose exec api psql "$DATABASE_URL" -f src/db/schema.sql
else
    echo "Database schema file not found, skipping migration."
fi

# Start Go Gateway in background
cd /app/services/go-gateway
go build -o gateway ./cmd/server
./gateway &

# Start Agent Orchestrator in background
cd /app/services/agent-orchestrator
./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001 --workers 2 &

# Start API Gateway
cd /app/apps/api
npm run build
node dist/index.js &

# Start Web Frontend
cd /app/apps/web
npm run build
NODE_ENV=production PORT=3001 node apps/web/server.js
EOF
chmod +x /app/init-databases.sh

# Expose all service ports
EXPOSE 3000 3001 8001 8080 5432 6379 7474 7687

# Default command
CMD ["/bin/bash", "/app/init-databases.sh"]
