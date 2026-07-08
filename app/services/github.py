import asyncio
import base64
from typing import Any

import httpx

class GitHubService:

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str) -> None:
        self._token = token
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    async def _get(self, path: str, **kwargs: Any) -> Any:
        response = await self._client.get(path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def _post(self, path: str, **kwargs: Any) -> Any:
        response = await self._client.post(path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def _delete(self, path: str, **kwargs: Any) -> None:
        response = await self._client.delete(path, **kwargs)
        response.raise_for_status()

    async def get_authenticated_user(self) -> dict:
        return await self._get("/user")

    async def get_user_orgs(self) -> list[dict]:
        return await self._get("/user/orgs", params={"per_page": 100})

    async def get_org_repos(self, org: str, per_page: int = 100) -> list[dict]:
        repos: list[dict] = []
        page = 1
        while True:
            batch = await self._get(
                f"/orgs/{org}/repos",
                params={"per_page": per_page, "page": page, "type": "all"},
            )
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
        return repos

    async def get_installation_repos(self, per_page: int = 100) -> list[dict]:
        repos: list[dict] = []
        page = 1
        while True:
            data = await self._get(
                "/installation/repositories",
                params={"per_page": per_page, "page": page},
            )
            batch = data.get("repositories", [])
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
        return repos

    async def get_repo_workflows(self, owner: str, repo: str) -> list[dict]:
        data = await self._get(f"/repos/{owner}/{repo}/actions/workflows")
        return data.get("workflows", [])

    async def get_workflow_runs(
        self,
        owner: str,
        repo: str,
        workflow_id: int,
        per_page: int = 30,
    ) -> list[dict]:
        data = await self._get(
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs",
            params={"per_page": per_page},
        )
        return data.get("workflow_runs", [])

    async def get_run_logs_url(self, owner: str, repo: str, run_id: int) -> str:
        response = await self._client.get(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/logs",
            follow_redirects=False,
        )
        if response.status_code in (301, 302, 307, 308):
            return response.headers["location"]
        response.raise_for_status()
        return str(response.url)

    async def get_run_logs_text(
        self, owner: str, repo: str, run_id: int, max_lines: int = 1000
    ) -> str:
        import io
        import zipfile

        response = await self._client.get(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/logs",
            follow_redirects=True,
        )
        response.raise_for_status()

        lines: list[str] = []
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                for name in sorted(zf.namelist()):
                    if name.endswith(".txt"):
                        content = zf.read(name).decode("utf-8", errors="replace")
                        lines.append(f"===== {name} =====")
                        lines.extend(content.splitlines())
        except zipfile.BadZipFile:
            lines = response.text.splitlines()

        if len(lines) > max_lines:
            lines = lines[-max_lines:]
        return "\n".join(lines)

    async def get_workflow_file(
        self, owner: str, repo: str, path: str, ref: str
    ) -> str:
        response = await self._client.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github.raw+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        response.raise_for_status()
        return response.text

    async def get_file_sha(self, owner: str, repo: str, path: str, ref: str) -> str | None:
        try:
            data = await self._get(f"/repos/{owner}/{repo}/contents/{path}", params={"ref": ref})
            if isinstance(data, dict):
                return data.get("sha")
            return None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    async def get_branch_head_sha(self, owner: str, repo: str, branch: str) -> str:
        data = await self._get(f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
        return data["object"]["sha"]

    async def create_fix_branch(self, owner: str, repo: str, base_sha: str, branch_name: str) -> None:
        try:
            await self._post(
                f"/repos/{owner}/{repo}/git/refs",
                json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 422 and "already exists" in exc.response.text:
                response = await self._client.patch(
                    f"/repos/{owner}/{repo}/git/refs/heads/{branch_name}",
                    json={"sha": base_sha, "force": True},
                )
                response.raise_for_status()
                return
            raise

    async def commit_fix(
        self,
        owner: str,
        repo: str,
        branch: str,
        path: str,
        content: str,
        message: str,
        current_sha: str | None,
    ) -> None:
        encoded = base64.b64encode(content.encode()).decode()
        payload: dict = {"message": message, "content": encoded, "branch": branch}
        if current_sha:
            payload["sha"] = current_sha

        delays = [0.5, 1.0, 2.0]
        for attempt, delay in enumerate([0.0, *delays]):
            if delay:
                await asyncio.sleep(delay)
            response = await self._client.put(f"/repos/{owner}/{repo}/contents/{path}", json=payload)
            if response.status_code != 404 or attempt == len(delays):
                response.raise_for_status()
                return

    async def create_pr(
        self, owner: str, repo: str, head: str, base: str, title: str, body: str
    ) -> dict:
        return await self._post(
            f"/repos/{owner}/{repo}/pulls",
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": base,
                "maintainer_can_modify": True,
            },
        )

    async def create_webhook(self, org: str, secret: str, url: str) -> dict:
        return await self._post(
            f"/orgs/{org}/hooks",
            json={
                "name": "web",
                "active": True,
                "events": ["workflow_run"],
                "config": {
                    "url": url,
                    "content_type": "json",
                    "secret": secret,
                    "insecure_ssl": "0",
                },
            },
        )

    async def delete_webhook(self, org: str, hook_id: int) -> None:
        await self._delete(f"/orgs/{org}/hooks/{hook_id}")

    async def aclose(self) -> None:
        await self._client.aclose()
