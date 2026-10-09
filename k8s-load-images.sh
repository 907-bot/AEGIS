#!/bin/bash
set -e

echo "📦 Loading Docker images into Kubernetes..."
echo ""

# Check if Docker Desktop's Kubernetes is running
if ! kubectl config current-context | grep -q docker-desktop; then
    echo "⚠️  Warning: You may not be using Docker Desktop's Kubernetes"
    echo "Current context: $(kubectl config current-context)"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Loading images..."

# Load each image
docker image load < <(docker save aegis-api:latest) 2>/dev/null || true
docker image load < <(docker save aegis-web:latest) 2>/dev/null || true
docker image load < <(docker save aegis-agent-orchestrator:latest) 2>/dev/null || true
docker image load < <(docker save aegis-go-gateway:latest) 2>/dev/null || true

echo ""
echo "✅ Images loaded!"
echo ""
echo "🔄 Restarting deployments to pull new images..."
kubectl rollout restart deployment/api -n aegis
kubectl rollout restart deployment/web -n aegis
kubectl rollout restart deployment/agent-orchestrator -n aegis
kubectl rollout restart deployment/go-gateway -n aegis

echo ""
echo "⏳ Waiting for pods to start..."
sleep 5

echo ""
kubectl get pods -n aegis
