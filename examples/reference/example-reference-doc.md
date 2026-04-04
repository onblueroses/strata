<!-- keywords: deployment, kubernetes, docker-compose, container -->
# Deployment Guide

Reference doc for container-based deployment. The `context-doc-router` hook matches
keywords above against the user's prompt and injects this doc's Quick Nav section.

## Quick Nav

| Section | Jump to | Read when |
|---------|---------|-----------|
| Docker setup | [Docker](#docker) | Building or debugging containers |
| Kubernetes | [Kubernetes](#kubernetes) | Deploying to k8s clusters |
| Environment | [Environment](#environment-variables) | Configuring secrets or env vars |

## Docker

Build and run with Docker Compose:

```bash
docker-compose up -d
docker-compose logs -f app
```

## Kubernetes

Apply manifests:

```bash
kubectl apply -f k8s/
kubectl rollout status deployment/app
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | yes | PostgreSQL connection string |
| `PORT` | no | Server port (default: 3000) |
