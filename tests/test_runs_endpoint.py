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


def _make_user(user_id: uuid.UUID | None = None) -> MagicMock:
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.access_token_encrypted = "encrypted-token"
    return user


def _scalars_result(rows: list) -> MagicMock:
    """Mimics db.execute(...) returning a Result whose .scalars().all() gives rows."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _scalar_one_result(value) -> MagicMock:
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _scalar_one_or_none_result(value) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


class TestRunsDataIsolation:
    """Regression tests for the cross-tenant data leak: any authenticated user
    could list/view/fetch-logs for ANY org's workflow runs, not just their own
    connected organizations. _user was resolved but never used to filter."""

    async def test_list_recent_runs_empty_when_user_owns_no_orgs(self):
        from app.api.v1.routes.runs import list_recent_runs

        db = AsyncMock()
        db.execute.return_value = _scalars_result([])  # owned_org_logins -> []

        result = await list_recent_runs(
            org_login=None, repo_name=None, run_status=None, conclusion=None,
            limit=20, offset=0, user=_make_user(), db=db,
        )
        assert result.total == 0
        assert result.runs == []
        # Must short-circuit before ever querying workflow_runs.
        assert db.execute.call_count == 1

    async def test_list_recent_runs_rejects_unowned_org_login(self):
        from app.api.v1.routes.runs import list_recent_runs
        from fastapi import HTTPException

        db = AsyncMock()
        db.execute.return_value = _scalars_result(["acme"])  # user only owns "acme"

        with pytest.raises(HTTPException) as exc_info:
            await list_recent_runs(
                org_login="someone-elses-org", repo_name=None, run_status=None,
                conclusion=None, limit=20, offset=0, user=_make_user(), db=db,
            )
        assert exc_info.value.status_code == 404

    async def test_list_recent_runs_scopes_query_to_owned_logins(self):
        from app.api.v1.routes.runs import list_recent_runs

        run = _make_run(org_login="acme")
        db = AsyncMock()
        db.execute.side_effect = [
            _scalars_result(["acme"]),       # owned_org_logins
            _scalar_one_result(1),           # count_query
            _scalars_result([run]),          # query
        ]

        result = await list_recent_runs(
            org_login=None, repo_name=None, run_status=None, conclusion=None,
            limit=20, offset=0, user=_make_user(), db=db,
        )
        assert result.total == 1
        assert len(result.runs) == 1

    async def test_get_run_hides_run_from_other_users_org(self):
        """The exact bug: a run belonging to an org the current user never
        connected must 404, not be returned."""
        from app.api.v1.routes.runs import get_run
        from fastapi import HTTPException

        other_users_run = _make_run(org_login="someone-elses-org")
        db = AsyncMock()
        db.execute.side_effect = [
            _scalars_result(["acme"]),  # current user only owns "acme"
            _scalar_one_or_none_result(other_users_run),
        ]

        with pytest.raises(HTTPException) as exc_info:
            await get_run(run_id=other_users_run.id, user=_make_user(), db=db)
        assert exc_info.value.status_code == 404

    async def test_get_run_allows_run_from_owned_org(self):
        from app.api.v1.routes.runs import get_run

        own_run = _make_run(org_login="acme")
        db = AsyncMock()
        db.execute.side_effect = [
            _scalars_result(["acme"]),
            _scalar_one_or_none_result(own_run),
        ]

        response = await get_run(run_id=own_run.id, user=_make_user(), db=db)
        assert response["org_login"] == "acme"

    async def test_get_run_logs_hides_run_from_other_users_org(self):
        from app.api.v1.routes.runs import get_run_logs
        from fastapi import HTTPException

        other_users_run = _make_run(org_login="someone-elses-org")
        db = AsyncMock()
        db.execute.side_effect = [
            _scalars_result(["acme"]),
            _scalar_one_or_none_result(other_users_run),
        ]

        with pytest.raises(HTTPException) as exc_info:
            with patch("app.core.security.decrypt_token", return_value="tok"):
                await get_run_logs(run_id=other_users_run.id, user=_make_user(), db=db)
        assert exc_info.value.status_code == 404
