"""Pipeline endpoints — V2 content pipeline."""
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from ..config import settings
from ..db_client import db
from ..dependencies import get_current_user, require_expert_owner
from ..content_pipeline.skill_loader import SkillRegistry

router = APIRouter(prefix="/api", tags=["pipeline"])

_skill_registry: SkillRegistry | None = None


def _get_skill_registry() -> SkillRegistry:
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry(Path(__file__).parent.parent / "content_pipeline" / "agents")
    return _skill_registry


@router.get("/skills")
async def list_skills():
    registry = _get_skill_registry()
    return {"skills": registry.list_all()}


@router.get("/skills/{agent}/{skill}/evolution")
async def skill_evolution(agent: str, skill: str):
    registry = _get_skill_registry()
    try:
        s = registry.get(agent, skill)
        return {"skill": s.name, "agent": s.agent, "version": s.version, "evolution_log": s.evolution_log}
    except KeyError:
        raise HTTPException(404, "Skill not found")
