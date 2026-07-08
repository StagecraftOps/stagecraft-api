from fastapi import APIRouter

from app.api.v1.routes import (
    agent_runs,
    analytics,
    application_contexts,
    applications,
    audit,
    auth,
    chat,
    custom_agents,
    dependency_graph,
    governance,
    insights,
    optimization,
    orgs,
    performance,
    pr_reviews,
    remediations,
    runs,
    standardization,
    vulnerabilities,
    workflows,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(orgs.router, prefix="/orgs", tags=["organizations"])
api_router.include_router(applications.router, prefix="/orgs", tags=["applications"])
api_router.include_router(custom_agents.router, prefix="/orgs", tags=["custom-agents"])
api_router.include_router(dependency_graph.router, prefix="/orgs", tags=["dependency-graph"])
api_router.include_router(performance.router, prefix="/orgs", tags=["performance"])
api_router.include_router(standardization.router, prefix="/orgs", tags=["standardization"])
api_router.include_router(governance.router, prefix="/orgs", tags=["governance"])
api_router.include_router(optimization.router, prefix="", tags=["optimization"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(remediations.router, prefix="/remediations", tags=["remediations"])
api_router.include_router(pr_reviews.router, prefix="/pr-reviews", tags=["pr-reviews"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(agent_runs.router, prefix="/agent-runs", tags=["agent-runs"])
api_router.include_router(application_contexts.router, prefix="/application-contexts", tags=["application-contexts"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(vulnerabilities.router, prefix="/vulnerabilities", tags=["vulnerabilities"])
api_router.include_router(insights.router, prefix="/insights", tags=["insights"])
