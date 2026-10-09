#!/bin/bash
set -e

echo "🚀 Deploying AEGIS to Kubernetes..."

# Create namespace and schema
echo "📦 Creating namespace and schema..."
kubectl apply -f k8s-manifests/00-namespace.yaml

# Create config and secrets
echo "🔐 Creating ConfigMaps and Secrets..."
kubectl apply -f k8s-manifests/01-config-secrets.yaml

# Create PVCs
echo "💾 Creating Persistent Volumes..."
kubectl apply -f k8s-manifests/02-pvcs.yaml

# Create database services
echo "🗄️ Deploying PostgreSQL..."
kubectl apply -f k8s-manifests/03-postgres.yaml

echo "📍 Deploying Redis..."
kubectl apply -f k8s-manifests/04-redis.yaml

echo "🕸️ Deploying Neo4j..."
kubectl apply -f k8s-manifests/05-neo4j.yaml

echo "🦙 Deploying Ollama..."
kubectl apply -f k8s-manifests/10-ollama.yaml

# Quick check (don't wait long)
echo "⏳ Checking database pods... (this may take a minute)"
sleep 5
kubectl get pods -n aegis

# Deploy application services (databases can still be starting)
echo ""
echo "🔌 Deploying API..."
kubectl apply -f k8s-manifests/06-api.yaml

echo "🎨 Deploying Web UI..."
kubectl apply -f k8s-manifests/07-web.yaml

echo "🤖 Deploying Agent Orchestrator..."
kubectl apply -f k8s-manifests/08-agent-orchestrator.yaml

echo "🚪 Deploying Go Gateway..."
kubectl apply -f k8s-manifests/09-go-gateway.yaml

# Wait for deployments with shorter timeout
echo ""
echo "⏳ Waiting for deployments (timeout: 60s)..."
kubectl rollout status deployment/redis -n aegis --timeout=60s || echo "⚠️ Redis still starting..."
kubectl rollout status deployment/api -n aegis --timeout=60s || echo "⚠️ API still starting..."
kubectl rollout status deployment/web -n aegis --timeout=60s || echo "⚠️ Web still starting..."
kubectl rollout status deployment/ollama -n aegis --timeout=60s || echo "⚠️ Ollama still starting..."

echo ""
echo "📋 Current pod status:"
kubectl get pods -n aegis
echo ""

echo "✅ Deployment initiated!"
echo ""
echo "📊 Get service endpoints:"
kubectl get svc -n aegis
echo ""
echo "🔍 Watch logs:"
echo "  kubectl logs -f deployment/api -n aegis"
echo "  kubectl logs -f deployment/web -n aegis"
echo "  kubectl logs -f deployment/postgres -n aegis"
echo ""
echo "⏳ Databases may take 1-2 minutes to start. Check status with:"
echo "  kubectl get pods -n aegis"
echo ""
