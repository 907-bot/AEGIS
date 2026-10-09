#!/bin/bash
set -e

echo "🚀 AEGIS Kubernetes Quick Start"
echo ""

# Check kubectl
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl first."
    exit 1
fi

echo "✅ kubectl found"
kubectl version --short

echo ""
echo "📋 Available options:"
echo ""
echo "1️⃣  Deploy with local images (Docker Desktop only):"
echo "   ./k8s-deploy.sh"
echo ""
echo "2️⃣  Push to Docker Hub and deploy:"
echo "   ./k8s-push-images.sh docker.io YOUR_USERNAME"
echo "   # Then update and re-deploy"
echo ""
echo "3️⃣  Check deployment status:"
echo "   kubectl get pods -n aegis"
echo "   kubectl get svc -n aegis"
echo ""
echo "4️⃣  View logs:"
echo "   kubectl logs -f deployment/api -n aegis"
echo ""
echo "5️⃣  Port forward to access locally:"
echo "   kubectl port-forward svc/web 3007:3001 -n aegis"
echo "   kubectl port-forward svc/api 3008:3000 -n aegis"
echo ""
