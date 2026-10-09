#!/bin/bash
# deploy-docker.sh - Script to deploy AEGIS using Docker Compose

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Main deployment function
deploy_docker() {
    print_info "Starting AEGIS Docker deployment..."
    
    # Check if docker-compose is available
    if ! command -v docker-compose &> /dev/null; then
        print_error "docker-compose is not installed. Please install Docker Compose."
        exit 1
    fi
    
    # Check Docker version
    if ! docker --version &> /dev/null; then
        print_error "Docker is not installed. Please install Docker."
        exit 1
    fi
    
    # Check system resources (cross-platform)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        local mem_total=$(sysctl -n hw.memsize 2>/dev/null | awk '{print int($1/1024/1024)}')
    else
        # Linux
        local mem_total=$(free -m 2>/dev/null | awk '/^Mem:/ {print $2}')
    fi
    if [ -n "$mem_total" ] && [ "$mem_total" -lt 4096 ]; then
        print_warn "System has less than 4GB RAM (${mem_total}MB). AEGIS may not work properly."
    fi
    
    # Navigate to the AEGIS directory (auto-detect)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$SCRIPT_DIR" || {
        print_error "AEGIS directory not found. Please check the path."
        exit 1
    }
    
    # Create .env file if it doesn't exist
    if [ ! -f .env ]; then
        print_warn ".env file not found. Creating from .env.example..."
        if [ -f .env.example ]; then
            cp .env.example .env
            print_info ".env file created. Please edit it and add your API keys."
        else
            print_warn ".env.example not found. You may need to set environment variables manually."
        fi
    fi
    
    # Check for Ollama-specific configuration
    if [ -f .env ]; then
        # Check if Ollama is configured
        if grep -q "OLLAMA_API_URL" .env && ! grep -q "^#.*OLLAMA_API_URL" .env; then
            print_info "Ollama configuration detected in .env"
            # Pull gemma4 model if Ollama is configured
            print_info "Checking for gemma4 model in Ollama..."
            ollama pull gemma4:latest 2>/dev/null || {
                print_warn "Failed to pull gemma4 model. You may need to run: ollama pull gemma4:latest"
                print_info "Make sure Ollama is running with: ollama serve &"
            }
        fi
    fi
    
    # Load environment variables
    if [ -f .env ]; then
        set -a
        source .env
        set +a
    fi
    
    # Check for Ollama configuration
    if [ -f .env ] && grep -q "OLLAMA_API_URL" .env && ! grep -q "^#.*OLLAMA_API_URL" .env; then
        print_info "Ollama configuration detected. Starting Ollama service..."
        # Start Ollama service
        docker-compose up -d ollama
        print_info "Waiting for Ollama to initialize..."
        sleep 30
        # Check if gemma4 is available
        docker-compose exec ollama curl -s "http://localhost:11434/api/tags" | grep -q "gemma4" && print_info "✅ Ollama gemma4 model available" || {
            print_warn "⚠️  gemma4 model not found in Ollama. You may need to run: docker-compose exec ollama ollama pull gemma4:latest"
        }
    fi
    
    print_info "Starting all services with Docker Compose..."
    print_info "This will build images and start: <co>PostgreSQL, Redis, Neo4j, Ollama (if configured), API Gateway, Agent Orchestrator, Go Gateway, and Frontend.</co: 4:[0]>"
    
    # Start infrastructure services first
    docker-compose up -d postgres redis neo4j
    
    # Wait for databases to initialize
    print_info "Waiting for databases to initialize..."
    print_info "This may take 60-90 seconds for Neo4j..."
    sleep 90
    
    # Check database connectivity
    print_info "Testing database connectivity..."
    docker-compose exec postgres pg_isready -U postgres
    docker-compose exec redis redis-cli ping
    docker-compose exec neo4j wget --quiet --tries=1 --spider http://localhost:7474
    
    # Initialize database schema
    print_info "Initializing database schema..."
    print_info "Running migration..."
    docker-compose up -d api
    sleep 15
    docker-compose exec api psql "$DATABASE_URL" -f src/db/schema.sql
    print_info "Database migration completed!"
    
    # Start application services (web, agent-orchestrator, go-gateway)
    print_info "Starting application services..."
    docker-compose up -d web agent-orchestrator go-gateway
    
    # Wait for web service to build
    print_info "Waiting for web service to build..."
    sleep 60
    
    # Wait for databases to initialize
    print_info "Waiting for databases to initialize..."
    print_info "This may take 60-90 seconds for Neo4j..."
    sleep 90
    
    # Check if services are running
    print_info "Checking service status..."
    docker-compose ps
    
    # Check database connectivity
    print_info "Testing database connectivity..."
    docker-compose exec postgres pg_isready -U postgres
    docker-compose exec redis redis-cli ping
    docker-compose exec neo4j wget --quiet --tries=1 --spider http://localhost:7474
    
    # Initialize database schema
    print_info "Initializing database schema..."
    print_info "Running migration..."
    docker-compose exec api psql "$DATABASE_URL" -f src/db/schema.sql
    print_info "Database migration completed!"
    
    # Wait a bit for all services to stabilize
    print_info "Waiting for services to stabilize..."
    sleep 30
    
    # Check final status
    print_info "Deployment complete! Final service status:"
    docker-compose ps
    
    # Display service URLs
    print_info "\nAccess your AEGIS platform at:"
    print_info "  <co>Web Dashboard:      http://localhost:3007</co: 4:[0]>"
    print_info "  <co>API Gateway:       http://localhost:3000</co: 4:[0]>"
    print_info "  <co>Agent Orchestrator: http://localhost:8001</co: 4:[0]>"
    print_info "  <co>Go Gateway:        http://localhost:8080</co: 4:[0]>"
    print_info "  <co>Neo4j Browser:     http://localhost:7474</co: 4:[0]>"
    
    # Health checks
    print_info "\nPerforming health checks..."
    
    # Check API health
    if docker-compose exec api curl -f http://localhost:3000/health/live > /dev/null 2>&1; then
        print_info "✅ API Gateway is healthy"
    else
        print_warn "⚠️  API Gateway health check failed"
    fi
    
    # Check Web Frontend health
    if docker-compose exec web curl -f http://localhost:3001 > /dev/null 2>&1; then
        print_info "✅ Web Frontend is healthy"
    else
        print_warn "⚠️  Web Frontend health check failed"
    fi
    
    # Check Agent Orchestrator health
    if docker-compose exec agent-orchestrator curl -f http://localhost:8001/health > /dev/null 2>&1; then
        print_info "✅ Agent Orchestrator is healthy"
    else
        print_warn "⚠️  Agent Orchestrator health check failed"
    fi
    
    # Check Go Gateway health
    if docker-compose exec go-gateway curl -f http://localhost:8080/health > /dev/null 2>&1; then
        print_info "✅ Go Gateway is healthy"
    else
        print_warn "⚠️  Go Gateway health check failed"
    fi
    
    print_info "\n🎉 AEGIS Docker deployment completed successfully!"
    print_info "\nUseful commands:"
    print_info "  View logs:     docker-compose logs -f [service-name]"
    print_info "  Restart:       docker-compose restart [service-name]"
    print_info "  Stop all:      docker-compose down"
    print_info "  Remove volumes: docker-compose down -v  (deletes all data!)"
}

# Function to stop and remove all services
stop_all() {
    print_info "Stopping all AEGIS services..."
    cd /path/to/aegis/AEGIS || {
        print_error "AEGIS directory not found."
        exit 1
    }
    
    docker-compose down
    print_info "All services stopped."
}

# Function to remove all data
remove_all_data() {
    print_warn "This will delete all data! This cannot be undone."
    read -p "Are you sure? Type 'DELETE' to confirm: " confirmation
    
    if [ "$confirmation" = "DELETE" ]; then
        print_info "Removing all AEGIS services and data..."
        cd /path/to/aegis/AEGIS || {
            print_error "AEGIS directory not found."
            exit 1
        }
        
        docker-compose down -v
        print_info "All services and data removed."
    else
        print_info "Operation cancelled."
    fi
}

# Function to view logs
view_logs() {
    local service_name=$1
    if [ -z "$service_name" ]; then
        print_info "Showing logs for all services..."
        docker-compose logs -f
    else
        print_info "Showing logs for service: $service_name"
        docker-compose logs -f "$service_name"
    fi
}

# Function to view service status
status() {
    print_info "Current AEGIS service status:"
    cd /path/to/aegis/AEGIS || {
        print_error "AEGIS directory not found."
        exit 1
    }
    
    docker-compose ps
}

# Main script logic
case "$1" in
    "deploy")
        deploy_docker
        ;;
    "stop")
        stop_all
        ;;
    "remove")
        remove_all_data
        ;;
    "logs")
        view_logs "$2"
        ;;
    "status")
        status
        ;;
    "health")
        status
        print_info "\nPerforming health checks..."
        
        # Check API health
        if docker-compose exec api curl -f http://localhost:3000/health/live > /dev/null 2>&1; then
            print_info "✅ API Gateway is healthy"
        else
            print_warn "⚠️  API Gateway health check failed"
        fi
        
        # Check Agent Orchestrator health
        if docker-compose exec agent-orchestrator curl -f http://localhost:8001/health > /dev/null 2>&1; then
            print_info "✅ Agent Orchestrator is healthy"
        else
            print_warn "⚠️  Agent Orchestrator health check failed"
        fi
        
        # Check Go Gateway health
        if docker-compose exec go-gateway curl -f http://localhost:8080/health > /dev/null 2>&1; then
            print_info "✅ Go Gateway is healthy"
        else
            print_warn "⚠️  Go Gateway health check failed"
        fi
        ;;
    *)
        echo "Usage: $0 {deploy|stop|remove|logs [service-name]|status|health}"
        echo ""
        echo "Commands:"
        echo "  deploy     Deploy AEGIS using Docker"
        echo "  stop       Stop all services and remove containers (keeps data)"
        echo "  remove     Stop all services and remove containers and data"
        echo "  logs       View logs (optional: service-name)"
        echo "  status     Show current service status"
        echo "  health     Show status and perform health checks"
        exit 1
        ;;
esac
