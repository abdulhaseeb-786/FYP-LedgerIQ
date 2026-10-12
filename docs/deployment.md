# Deployment Guide

## 1. Local Development Setup
```bash
cd deploy/compose
cp ../../backend/.env.example .env
docker compose up --build
```

API interactive documentation:
- Swagger UI: `http://localhost:8000/docs`
- Phase 2 Test Workbench: `http://localhost:8000/test`
- Health check: `http://localhost:8000/api/v1/health`

## 2. Production Deployment on a Single VPS
1. Provision Ubuntu 22.04 LTS VPS (2GB+ RAM).
2. Run production stack:
   ```bash
   docker compose -f deploy/compose/docker-compose.yml -f deploy/compose/docker-compose.prod.yml up -d
   ```
