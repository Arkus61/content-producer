"""Config loader for per-agent markdown configuration files."""
from __future__ import annotations

import os
import re
import yaml
from pathlib import Path
from typing import Any


def _extract_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter and markdown body from agent config file."""
    match = re.fullmatch(r"---\s*\n(.*?)\n---\s*\n?(.*)", text.strip(), re.DOTALL)
    if not match:
        return {}, text.strip()
    try:
        front = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        front = {}
    body = match.group(2).strip()
    return front, body


class AgentConfig:
    """Runtime configuration for a single agent loaded from AGENT-NN-NAME.md."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        text = self.path.read_text(encoding="utf-8")
        self.frontmatter, self.body = _extract_frontmatter(text)

    # ── frontmatter accessors ─────────────────────────────

    @property
    def id(self) -> str:
        return str(self.frontmatter.get("id", self.path.stem.lower()))

    @property
    def name(self) -> str:
        return str(self.frontmatter.get("name", self.id))

    @property
    def model(self) -> str:
        return str(self.frontmatter.get("model", "gpt-4o"))

    @property
    def api_key(self) -> str:
        raw = self.frontmatter.get("api_key", "${OPENAI_API_KEY}")
        if isinstance(raw, str) and raw.startswith("${") and raw.endswith("}"):
            env_var = raw[2:-1]
            return os.getenv(env_var, "")
        return str(raw)

    @property
    def temperature(self) -> float:
        return float(self.frontmatter.get("temperature", 0.7))

    @property
    def max_tokens(self) -> int:
        return int(self.frontmatter.get("max_tokens", 4096))

    @property
    def response_format(self) -> str | None:
        fmt = self.frontmatter.get("response_format")
        if fmt in ("json_object", "json"):
            return "json_object"
        return None

    @property
    def reflection_threshold(self) -> float:
        return float(self.frontmatter.get("reflection_threshold", 80.0))

    @property
    def max_iterations(self) -> int:
        return int(self.frontmatter.get("max_iterations", 3))

    @property
    def system_prompt(self) -> str:
        """Extract fenced ``` prompt block from body, or return body as-is."""
        # prefer fenced code block labeled as prompt
        code_match = re.search(r"```(?:\w*\n)?(.*?)\n```", self.body, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        return self.body.strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "model": self.model,
            "api_key": self.api_key,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": self.response_format,
            "reflection_threshold": self.reflection_threshold,
            "max_iterations": self.max_iterations,
            "system_prompt": self.system_prompt,
        }


class AgentRegistry:
    """Discovers and caches agent configs from the agents/ directory."""

    def __init__(self, agents_dir: str | Path | None = None) -> None:
        if agents_dir is None:
            agents_dir = Path(__file__).with_name("agents")
        self.dir = Path(agents_dir)
        self._configs: dict[str, AgentConfig] = {}
        self._discover()

    def _discover(self) -> None:
        """Scan *.md files and load those with `id` in frontmatter."""
        for path in sorted(self.dir.glob("AGENT-*.md")):
            try:
                cfg = AgentConfig(path)
                if cfg.id:
                    self._configs[cfg.id] = cfg
            except Exception:
                continue

    def get(self, agent_id: str) -> AgentConfig:
        if agent_id not in self._configs:
            raise KeyError(f"Agent config not found: {agent_id} in {self.dir}")
        return self._configs[agent_id]

    def keys(self) -> list[str]:
        return list(self._configs.keys())

    def all(self) -> list[AgentConfig]:
        return list(self._configs.values())
