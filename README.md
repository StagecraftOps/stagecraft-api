# agora-api

FastAPI backend for [aGorA](https://github.com/aGora-Ops) — handles GitHub OAuth, org management, workflow/run queries, remediations, WebSocket updates, and analytics.

**Port**: 8000 | **Part of**: [aGora-Ops](https://github.com/aGora-Ops)

## Quick start

```bash
cp .env.example .env   # fill in values
docker compose up --build
# API at http://localhost:8000 — docs at http://localhost:8000/docs
```

## Related repos

| Repo | Purpose |
|------|---------|
| [agora-webhook](https://github.com/aGora-Ops/agora-webhook) | GitHub webhook receiver → SQS |
| [agora-worker](https://github.com/aGora-Ops/agora-worker) | Celery worker — AI analysis via Bedrock |
| [agora-frontend](https://github.com/aGora-Ops/agora-frontend) | Next.js 14 dashboard |
| [agora-workflows](https://github.com/aGora-Ops/agora-workflows) | Reusable GitHub Actions |
| [agora-helm](https://github.com/aGora-Ops/agora-helm) | Helm charts for EKS |
| [agora-infra](https://github.com/aGora-Ops/agora-infra) | Terraform — AWS infrastructure |
