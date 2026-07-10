# stagecraft-api

FastAPI backend for [StageCraft](https://github.com/StagecraftOps) — the platform's single source of truth and the only service the frontend ever talks to.

**Port**: 8000 · **Stack**: FastAPI, async SQLAlchemy, Alembic, Postgres (pgvector), Redis

## What it does

- **Auth** — GitHub OAuth login, JWT session cookies, GitHub App installation handling (`auth.py`, `orgs.py`)
- **Core data** — organizations, applications (repo groupings with strict isolation), workflows, runs (`applications.py`, `workflows.py`, `runs.py`)
- **Analysis surfaces** — remediations (with pgvector semantic search), vulnerabilities, optimization, performance, standardization, governance, dependency graph, insights, PR reviews, agent runs (one route module each under `app/api/v1/routes/`)
- **Pipeline Chat** — natural-language questions over pipeline data via Bedrock (`chat.py`)
- **Live updates** — WebSocket relay fed by Redis pub/sub; the worker publishes, the API fans out to connected dashboards (`websocket.py`)
- **Internal API** — endpoints the worker calls back into, protected by `INTERNAL_API_KEY` (`internal.py`)

## How it fits the platform

```
frontend (3000) ──HTTP/WS──▶ api (8000) ──▶ Postgres (pgvector), Redis
                                  ▲
worker ── internal API + Redis pub/sub
```

The API never talks to SQS or runs analysis itself — that's [stagecraft-worker](https://github.com/StagecraftOps/stagecraft-worker). Events arrive via [stagecraft-webhook](https://github.com/StagecraftOps/stagecraft-webhook) → SQS → worker → (internal API + Redis) → WebSocket.

## What it needs

| Dependency | Why |
|---|---|
| Postgres with `pgvector` | All persistence + semantic search over remediations |
| Redis | WebSocket pub/sub relay, cache |
| GitHub OAuth app + GitHub App | Login and org/repo access (`GITHUB_CLIENT_ID/SECRET`, `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_APP_SLUG`) |
| AWS Bedrock | Pipeline Chat (`BEDROCK_CHAT_MODEL_ID`; auth via IRSA, `BEDROCK_API_KEY`, or `BEDROCK_CROSS_ACCOUNT_ROLE_ARN`) |
| Secrets | `SECRET_KEY` (JWT), `TOKEN_ENCRYPTION_KEY` (Fernet for stored GitHub tokens), `INTERNAL_API_KEY` (shared with worker) |

Full list with defaults: `app/core/config.py`. Optional extras: Bedrock knowledge base (`BEDROCK_KB_ID`), guardrails, Neo4j graph backend (`GRAPH_BACKEND=neo4j`).

## Run locally

```bash
cp .env.example .env   # fill in GitHub + secret values
docker compose up --build
# API at http://localhost:8000 — interactive docs at /docs
```

Migrations run via Alembic: `alembic upgrade head` (the Helm chart does this automatically in a pre-upgrade Job).

Tests: `pytest tests/`

## API documentation

Swagger UI at `/docs`, ReDoc at `/redoc`, schema at `/openapi.json` — auto-generated from the route definitions. Disabled when `ENVIRONMENT=prod`/`production` (see `Settings.is_production`) so the internal schema isn't exposed publicly.

## Related repos

| Repo | Purpose |
|------|---------|
| [stagecraft-webhook](https://github.com/StagecraftOps/stagecraft-webhook) | GitHub webhook receiver → SQS |
| [stagecraft-worker](https://github.com/StagecraftOps/stagecraft-worker) | Celery worker — analysis agents via Bedrock |
| [stagecraft-frontend](https://github.com/StagecraftOps/stagecraft-frontend) | Angular dashboard |
| [stagecraft-mcp](https://github.com/StagecraftOps/stagecraft-mcp) | MCP server — GitHub tools for the agents |
| [stagecraft-helm](https://github.com/StagecraftOps/stagecraft-helm) | Helm charts for EKS |
| [stagecraft-infra](https://github.com/StagecraftOps/stagecraft-infra) | Terraform — AWS infrastructure |
