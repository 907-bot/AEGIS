#!/bin/bash
set -e

REGISTRY="${1:-docker.io}"
USERNAME="${2:-YOUR_DOCKER_USERNAME}"

echo "📦 Tagging and pushing AEGIS images to $REGISTRY/$USERNAME"
echo ""

# Tag images
echo "🏷️  Tagging images..."
docker tag aegis-api:latest $REGISTRY/$USERNAME/aegis-api:latest
docker tag aegis-web:latest $REGISTRY/$USERNAME/aegis-web:latest
docker tag aegis-agent-orchestrator:latest $REGISTRY/$USERNAME/aegis-agent-orchestrator:latest
docker tag aegis-go-gateway:latest $REGISTRY/$USERNAME/aegis-go-gateway:latest

# Push images
echo "🚀 Pushing images (this may take a few minutes)..."
docker push $REGISTRY/$USERNAME/aegis-api:latest
docker push $REGISTRY/$USERNAME/aegis-web:latest
docker push $REGISTRY/$USERNAME/aegis-agent-orchestrator:latest
docker push $REGISTRY/$USERNAME/aegis-go-gateway:latest

echo ""
echo "✅ Images pushed successfully!"
echo ""
echo "📝 Next steps:"
echo "1. Update k8s-manifests to use your registry:"
echo "   sed -i 's|image: aegis-|image: $REGISTRY/$USERNAME/aegis-|g' k8s-manifests/*.yaml"
echo "   sed -i 's|imagePullPolicy: Never|imagePullPolicy: Always|g' k8s-manifests/*.yaml"
echo ""
echo "2. Re-deploy:"
echo "   ./k8s-deploy.sh"
echo ""
