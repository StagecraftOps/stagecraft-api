from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.routes.orgs import _get_owned_org
from app.db.base import get_db
from app.models.custom_agent_config import CustomAgentConfig
from app.models.user import User

router = APIRouter()

class SkillFile(BaseModel):
    name: str
    content: str

class CustomAgentConfigUpdate(BaseModel):
    system_prompt: str | None = None
    skill_files: list[SkillFile] = []
    repo_name: str = ""

def _serialize(config: CustomAgentConfig | None, agent_key: str, repo_name: str) -> dict:
    if not config:
        return {"agent_key": agent_key, "repo_name": repo_name, "system_prompt": None, "skill_files": [], "updated_at": None}
    return {
        "agent_key": config.agent_key,
        "repo_name": config.repo_name,
        "system_prompt": config.system_prompt,
        "skill_files": config.skill_files or [],
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }

@router.get("/{org_login}/custom-agents/{agent_key}")
async def get_custom_agent_config(
    org_login: str,
    agent_key: str,
    repo_name: str = Query(default=""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _get_owned_org(org_login, user, db)
    result = await db.execute(
        select(CustomAgentConfig).where(
            CustomAgentConfig.org_login == org_login,
            CustomAgentConfig.agent_key == agent_key,
            CustomAgentConfig.repo_name == repo_name,
        )
    )
    config = result.scalar_one_or_none()
    if not config and repo_name:
        # Fall back to the org-wide default config when no repo-specific row exists.
        result = await db.execute(
            select(CustomAgentConfig).where(
                CustomAgentConfig.org_login == org_login,
                CustomAgentConfig.agent_key == agent_key,
                CustomAgentConfig.repo_name == "",
            )
        )
        config = result.scalar_one_or_none()
    return _serialize(config, agent_key, repo_name)

@router.put("/{org_login}/custom-agents/{agent_key}")
async def update_custom_agent_config(
    org_login: str,
    agent_key: str,
    body: CustomAgentConfigUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org = await _get_owned_org(org_login, user, db)
    result = await db.execute(
        select(CustomAgentConfig).where(
            CustomAgentConfig.org_login == org_login,
            CustomAgentConfig.agent_key == agent_key,
            CustomAgentConfig.repo_name == body.repo_name,
        )
    )
    config = result.scalar_one_or_none()
    skill_files = [f.model_dump() for f in body.skill_files]
    if config:
        config.system_prompt = body.system_prompt
        config.skill_files = skill_files
    else:
        config = CustomAgentConfig(
            org_id=org.id,
            org_login=org_login,
            agent_key=agent_key,
            repo_name=body.repo_name,
            system_prompt=body.system_prompt,
            skill_files=skill_files,
        )
        db.add(config)
    await db.commit()
    await db.refresh(config)
    return _serialize(config, agent_key, body.repo_name)
