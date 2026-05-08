"""Skill loader: parses SKILL.md files with YAML frontmatter and learned patterns."""
from __future__ import annotations

import re
import yaml
from pathlib import Path
from typing import Any


def _extract_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = re.fullmatch(r"---\s*\n(.*?)\n---\s*\n?(.*)", text.strip(), re.DOTALL)
    if not match:
        return {}, text.strip()
    try:
        front = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        front = {}
    return front, match.group(2).strip()


def _extract_section(text: str, heading: str) -> str:
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _parse_learned_patterns(text: str) -> list[dict[str, Any]]:
    section = _extract_section(text, "Learned Patterns")
    if not section:
        return []
    try:
        return yaml.safe_load(section) or []
    except yaml.YAMLError:
        return []


def _parse_evolution_log(text: str) -> list[dict[str, Any]]:
    section = _extract_section(text, "Evolution Log")
    if not section:
        return []
    try:
        return yaml.safe_load(section) or []
    except yaml.YAMLError:
        return []


class Skill:
    """Runtime representation of a loaded skill."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        raw = self.path.read_text(encoding="utf-8")
        self.frontmatter, self.body = _extract_frontmatter(raw)
        self.name: str = self.frontmatter.get("skill", self.path.stem)
        self.version: int = int(self.frontmatter.get("version", 1))
        self.agent: str = self.frontmatter.get("agent", "")
        self.category: str = self.frontmatter.get("category", "")
        self.base_prompt: str = _extract_section(self.body, "Base Prompt")
        self.learned_patterns: list[dict[str, Any]] = _parse_learned_patterns(self.body)
        self.evolution_log: list[dict[str, Any]] = _parse_evolution_log(self.body)

    def build_prompt(self, **variables) -> str:
        prompt = self.base_prompt.format(**variables)
        if self.learned_patterns:
            lines = ["\n## Learned Patterns (apply these weights):"]
            for p in self.learned_patterns:
                w = p.get("weight", "0%")
                lines.append(f"- {p.get('pattern', '')} (weight: {w})")
            prompt += "\n".join(lines)
        return prompt

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "agent": self.agent,
            "category": self.category,
            "base_prompt": self.base_prompt[:200] + "..." if len(self.base_prompt) > 200 else self.base_prompt,
            "learned_patterns_count": len(self.learned_patterns),
            "evolution_entries": len(self.evolution_log),
        }


class SkillRegistry:
    """Discovers and caches skills from agent skill directories."""

    def __init__(self, agents_dir: str | Path) -> None:
        self.agents_dir = Path(agents_dir)
        self._skills: dict[str, dict[str, Skill]] = {}
        self._discover()

    def _discover(self) -> None:
        if not self.agents_dir.is_dir():
            return
        for agent_dir in sorted(self.agents_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            skills_dir = agent_dir / "skills"
            if not skills_dir.is_dir():
                continue
            agent_name = agent_dir.name
            self._skills[agent_name] = {}
            for skill_file in sorted(skills_dir.glob("*.md")):
                try:
                    skill = Skill(skill_file)
                    self._skills[agent_name][skill.name] = skill
                except Exception:
                    continue

    def get(self, agent_name: str, skill_name: str) -> Skill:
        if agent_name not in self._skills:
            raise KeyError(f"Agent '{agent_name}' not found in registry")
        if skill_name not in self._skills[agent_name]:
            raise KeyError(f"Skill '{skill_name}' not found for agent '{agent_name}'")
        return self._skills[agent_name][skill_name]

    def list_agent_skills(self, agent_name: str) -> list[str]:
        return list(self._skills.get(agent_name, {}).keys())

    def list_all(self) -> dict[str, list[str]]:
        return {agent: list(skills.keys()) for agent, skills in self._skills.items()}
