# AEGIS Kubernetes Deployment Guide

## Prerequisites

1. **Kubernetes cluster** (v1.20+)
   - Local: Docker Desktop, Minikube, or Kind
   - Cloud: EKS, GKE, AKS, DigitalOcean

2. **kubectl** configured to access your cluster

3. **Docker images** pushed to a registry or loaded locally:
   ```bash
   docker tag aegis-api:latest YOUR_REGISTRY/aegis-api:latest
   docker tag aegis-web:latest YOUR_REGISTRY/aegis-web:latest
   docker tag aegis-agent-orchestrator:latest YOUR_REGISTRY/aegis-agent-orchestrator:latest
   docker tag aegis-go-gateway:latest YOUR_REGISTRY/aegis-go-gateway:latest
   ```

## Quick Start

### Option 1: Local Kubernetes (Docker Desktop / Minikube)

```bash
# Enable Kubernetes in Docker Desktop (if using local images)
# Settings > Kubernetes > Enable Kubernetes

# Load images (if using local registry)
docker save aegis-api:latest | kubectl load image stream://aegis-api:latest -n aegis

# Deploy all services
./k8s-deploy.sh

# Check status
kubectl get pods -n aegis
kubectl get svc -n aegis
```

### Option 2: Cloud Kubernetes (EKS/GKE/AKS)

First, push images to your registry:
```bash
# Docker Hub
docker tag aegis-api:latest yourusername/aegis-api:latest
docker push yourusername/aegis-api:latest

# Then update k8s-manifests to use your registry and remove imagePullPolicy: Never
```

Then deploy:
```bash
./k8s-deploy.sh
```

## Deployment Structure

The deployment includes:

- **Namespace**: `aegis` - Isolated namespace for all AEGIS resources
- **Databases**:
  - PostgreSQL (1 replica) - 10Gi storage
  - Redis (1 replica) - 5Gi storage
  - Neo4j (1 replica) - 10Gi storage
  
- **Applications**:
  - API Service (2 replicas) - LoadBalancer on port 3008
  - Web UI (2 replicas) - LoadBalancer on port 3007
  - Agent Orchestrator (1 replica) - Internal service on port 8001
  - Go Gateway (1 replica) - LoadBalancer on port 8080

## Accessing Services

### Get LoadBalancer IPs:
```bash
kubectl get svc -n aegis
```

### Local access:
```bash
# Port forward to API
kubectl port-forward svc/api 3008:3008 -n aegis

# Port forward to Web
kubectl port-forward svc/web 3007:3001 -n aegis

# Then access:
# http://localhost:3007  (Web UI)
# http://localhost:3008  (API)
```

## Managing Deployments

### View logs:
```bash
kubectl logs -f deployment/api -n aegis
kubectl logs -f deployment/web -n aegis
kubectl logs -f deployment/agent-orchestrator -n aegis
```

### View pod details:
```bash
kubectl describe pod <pod-name> -n aegis
kubectl get pods -n aegis -o wide
```

### Scale replicas:
```bash
kubectl scale deployment api --replicas=3 -n aegis
kubectl scale deployment web --replicas=4 -n aegis
```

### Update environment variables:
```bash
# Edit ConfigMap
kubectl edit configmap aegis-config -n aegis

# Restart pods to apply changes
kubectl rollout restart deployment/api -n aegis
```

### Update image:
```bash
kubectl set image deployment/api api=yourusername/aegis-api:v2 -n aegis
```

## Monitoring & Debugging

### Check resource usage:
```bash
kubectl top nodes
kubectl top pods -n aegis
```

### Get events:
```bash
kubectl get events -n aegis --sort-by='.lastTimestamp'
```

### Execute commands in pod:
```bash
kubectl exec -it <pod-name> -n aegis -- /bin/sh
```

## Persistent Storage

Each service uses persistent volumes for data:

- **PostgreSQL**: `/var/lib/postgresql/data`
- **Redis**: `/data`
- **Neo4j**: `/data`

To check PVC status:
```bash
kubectl get pvc -n aegis
```

## Production Checklist

- [ ] Update database passwords in Secrets
- [ ] Add API keys for OpenAI/Gemini in Secrets
- [ ] Configure ingress for external access (instead of LoadBalancer)
- [ ] Set up resource limits and requests
- [ ] Enable network policies for security
- [ ] Configure horizontal pod autoscaling (HPA)
- [ ] Set up monitoring (Prometheus) and logging (ELK)
- [ ] Enable backup for PostgreSQL/Neo4j
- [ ] Configure RBAC policies
- [ ] Use private Docker registry

## Cleanup

```bash
# Delete all resources
kubectl delete namespace aegis

# Or delete specific services
kubectl delete deployment api -n aegis
kubectl delete svc web -n aegis
```

## Troubleshooting

### Pod not starting:
```bash
kubectl describe pod <pod-name> -n aegis
kubectl logs <pod-name> -n aegis
```

### Cannot connect to services:
```bash
# Test DNS resolution
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup api.aegis.svc.cluster.local

# Test connectivity
kubectl run -it --rm debug --image=busybox --restart=Never -- wget -O- http://api:3008/health/live
```

### Database connection issues:
```bash
# Check if databases are ready
kubectl get pods -n aegis | grep postgres
kubectl logs -f deployment/postgres -n aegis
```

## Next Steps

1. **Ingress Setup**: Use Nginx Ingress or AWS ALB for production access
2. **Autoscaling**: Set up HPA for API and Web deployments
3. **Monitoring**: Deploy Prometheus + Grafana
4. **Backup**: Implement automated database backups
5. **CI/CD**: Integrate with ArgoCD or Flux for GitOps
