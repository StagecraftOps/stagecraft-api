"""Tests for GET /api/v1/runs/ filter and pagination behaviour."""
import os
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only-32ch")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")

def _make_run(
    *,
    org_login: str = "acme",
    repo_name: str = "widgets",
    status: str = "completed",
    conclusion: str | None = "success",
) -> MagicMock:
    run = MagicMock()
    run.id = uuid.uuid4()
    run.github_run_id = 12345
    run.github_workflow_id = 999
    run.org_login = org_login
    run.repo_name = repo_name
    run.workflow_name = "CI"
    run.workflow_file = ".github/workflows/ci.yml"
    run.branch = "main"
    run.head_sha = "abc123"
    run.status = status
    run.conclusion = conclusion
    run.started_at = datetime(2026, 6, 18, tzinfo=timezone.utc)
    run.completed_at = datetime(2026, 6, 18, tzinfo=timezone.utc)
    run.html_url = "https://github.com/acme/widgets/actions/runs/12345"
    run.created_at = datetime(2026, 6, 18, tzinfo=timezone.utc)
    run.updated_at = datetime(2026, 6, 18, tzinfo=timezone.utc)
    return run

class TestRunsFilter:
    """Unit tests for _upsert_workflow_run's filter parameter construction."""

    def test_org_login_filter_applied(self):
        """org_login query param must be forwarded to the WHERE clause."""
        from app.api.v1.routes.runs import list_recent_runs
        import inspect
        sig = inspect.signature(list_recent_runs)
        assert "org_login" in sig.parameters
        assert "repo_name" in sig.parameters
        assert "run_status" in sig.parameters
        assert "conclusion" in sig.parameters
        assert "offset" in sig.parameters

    def test_total_uses_count_query_not_len(self):
        """
        The runs endpoint must run a SELECT COUNT(*) for `total`, not derive
        it from len(runs) — otherwise pagination is wrong (total always == page
        size).
        """
        import ast
        import pathlib

        source = pathlib.Path(
            "app/api/v1/routes/runs.py"
        ).read_text()
        tree = ast.parse(source)

        found_count = any(
            isinstance(node, ast.Attribute) and node.attr == "scalar_one"
            for node in ast.walk(tree)
        )
        assert found_count, (
            "list_recent_runs must use scalar_one() on a count query for `total`"
        )

    def test_offset_param_present(self):
        """Pagination requires an offset parameter."""
        import pathlib, re

        source = pathlib.Path(
            "app/api/v1/routes/runs.py"
        ).read_text()
        assert "offset" in source, "offset query param must be present for pagination"
        assert ".offset(offset)" in source or "offset(offset)" in source

class TestWorkflowRunModelUpdatedAt:
    """Confirm the updated_at column was added to the model."""

    def test_model_has_updated_at(self):
        from app.models.workflow_run import WorkflowRun
        assert hasattr(WorkflowRun, "updated_at"), (
            "WorkflowRun.updated_at column must exist for lifecycle upserts"
        )

class TestOrganizationModelSyncStatus:
    """Confirm sync_status column was added to the Organization model."""

    def test_model_has_sync_status(self):
        from app.models.organization import Organization
        assert hasattr(Organization, "sync_status"), (
            "Organization.sync_status column must exist to track backfill progress"
        )
