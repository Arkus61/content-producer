"""Memory Agent — knowledge graph with pgvector + JSON cache."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4
from collections import Counter

logger = logging.getLogger("content-producer.memory")


class MemoryAgent:
    """Manages expert knowledge graph: ingest, retrieve, housekeeping."""

    def __init__(self, db_client=None, data_dir: str | Path = "data/memory") -> None:
        self.db = db_client  # Supabase DB client or None for local-only
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # ── Ingest ──────────────────────────────────────────────

    async def ingest_run(self, expert_id: str, run_data: dict[str, Any]) -> dict[str, Any]:
        """Save a completed pipeline run and extract nodes/edges."""
        run_id = run_data.get("task_id") or str(uuid4())
        run_data["id"] = run_id
        run_data["expert_id"] = expert_id
        run_data["ingested_at"] = datetime.now(timezone.utc).isoformat()

        # Save to local JSONL
        self._append_jsonl(expert_id, run_data)

        # Extract nodes
        nodes = self._extract_nodes(expert_id, run_data)
        for node in nodes:
            self._append_jsonl(f"{expert_id}_nodes", node)

        # Extract edges
        edges = self._extract_edges(expert_id, run_data, nodes)
        for edge in edges:
            self._append_jsonl(f"{expert_id}_edges", edge)

        logger.info("Ingested run %s for expert %s: %d nodes, %d edges",
                     run_id, expert_id, len(nodes), len(edges))

        return {
            "run_id": run_id,
            "nodes_extracted": len(nodes),
            "edges_extracted": len(edges),
            "status": "ingested",
        }

    def _extract_nodes(self, expert_id: str, run_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract graph nodes from a pipeline run."""
        nodes = []
        now = datetime.now(timezone.utc).isoformat()
        topic = run_data.get("topic", "")
        platform = run_data.get("platform", "telegram")
        content_type = run_data.get("content_type", "post")

        # Topic node
        if topic:
            nodes.append({
                "id": str(uuid4()),
                "expert_id": expert_id,
                "agent_id": "memory",
                "node_type": "topic",
                "label": topic,
                "metadata": {"platform": platform, "content_type": content_type},
                "created_at": now,
                "last_confirmed_at": now,
                "evidence_count": 1,
                "confidence": 0.6,
                "is_archived": False,
            })

        # Score node
        score = run_data.get("final_score") or (run_data.get("score") or {}).get("overall")
        if isinstance(score, dict):
            score = score.get("overall")
        if score is not None:
            str_score = str(round(float(score)))
            nodes.append({
                "id": str(uuid4()),
                "expert_id": expert_id,
                "agent_id": "memory",
                "node_type": "metric",
                "label": f"score:{str_score}",
                "metadata": {
                    "score": float(score),
                    "iterations": run_data.get("iterations", 1),
                    "run_id": run_data.get("id"),
                },
                "created_at": now,
                "last_confirmed_at": now,
                "evidence_count": 1,
                "confidence": 0.8,
                "is_archived": False,
            })

        # Content node (first 100 chars as label)
        content = run_data.get("content") or run_data.get("draft") or ""
        if content and isinstance(content, str) and len(content) > 10:
            nodes.append({
                "id": str(uuid4()),
                "expert_id": expert_id,
                "agent_id": "memory",
                "node_type": "content",
                "label": content[:100] + ("..." if len(content) > 100 else ""),
                "metadata": {
                    "full_content": content,
                    "run_id": run_data.get("id"),
                },
                "created_at": now,
                "last_confirmed_at": now,
                "evidence_count": 1,
                "confidence": 0.7,
                "is_archived": False,
            })

        return nodes

    def _extract_edges(
        self, expert_id: str, run_data: dict[str, Any], nodes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Create edges between extracted nodes."""
        edges = []
        now = datetime.now(timezone.utc).isoformat()

        topic_nodes = [n for n in nodes if n["node_type"] == "topic"]
        score_nodes = [n for n in nodes if n["node_type"] == "metric"]
        content_nodes = [n for n in nodes if n["node_type"] == "content"]

        # Topic → Score
        for t in topic_nodes:
            for s in score_nodes:
                score_val = s["metadata"].get("score", 50)
                edges.append({
                    "id": str(uuid4()),
                    "expert_id": expert_id,
                    "from_node_id": t["id"],
                    "to_node_id": s["id"],
                    "relation": "achieves" if score_val >= 80 else "scored",
                    "weight": min(1.0, score_val / 100),
                    "evidence_count": 1,
                    "created_at": now,
                    "last_confirmed_at": now,
                    "is_tombstone": False,
                })

        # Topic → Content
        for t in topic_nodes:
            for c in content_nodes:
                edges.append({
                    "id": str(uuid4()),
                    "expert_id": expert_id,
                    "from_node_id": t["id"],
                    "to_node_id": c["id"],
                    "relation": "produced",
                    "weight": 0.7,
                    "evidence_count": 1,
                    "created_at": now,
                    "last_confirmed_at": now,
                    "is_tombstone": False,
                })

        return edges

    # ── Retrieve ────────────────────────────────────────────

    async def retrieve_context(
        self, expert_id: str, topic: str = "", limit: int = 10
    ) -> dict[str, Any]:
        """Return relevant context for the given expert and topic."""
        runs = self._read_jsonl(expert_id)

        # Filter by topic relevance
        if topic:
            topic_lower = topic.lower()
            runs = [r for r in runs if topic_lower in json.dumps(r).lower()]

        recent = sorted(
            runs, key=lambda r: r.get("ingested_at", ""), reverse=True
        )[:limit]

        # Extract high/low performers
        high_scores = []
        low_scores = []
        all_topics = Counter()

        for r in recent:
            t = r.get("topic", "")
            all_topics[t] += 1

            score = r.get("final_score")
            if isinstance(score, dict):
                score = score.get("overall")
            try:
                score = float(score) if score is not None else 0
            except (TypeError, ValueError):
                score = 0

            if score >= 80:
                high_scores.append({
                    "topic": t,
                    "score": score,
                    "platform": r.get("platform"),
                    "draft_preview": str(r.get("content") or r.get("draft") or "")[:200],
                })
            elif score <= 50:
                low_scores.append({
                    "topic": t,
                    "score": score,
                    "critique": str(r.get("critique") or "")[:200],
                })

        return {
            "expert_id": expert_id,
            "total_runs": len(runs),
            "recent_runs": len(recent),
            "top_performers": high_scores[:3],
            "low_performers": low_scores[:3],
            "common_topics": all_topics.most_common(5),
        }

    # ── Housekeeping ────────────────────────────────────────

    async def conflict_scan(self, expert_id: str) -> list[dict[str, Any]]:
        """Find contradictory facts and resolve by freshness/evidence."""
        nodes = self._read_jsonl(f"{expert_id}_nodes")
        conflicts = []

        # Group nodes by type
        by_type: dict[str, list[dict[str, Any]]] = {}
        for n in nodes:
            by_type.setdefault(n["node_type"], []).append(n)

        # Find conflicting labels within same type
        for node_type, type_nodes in by_type.items():
            if node_type != "topic":
                continue  # Only topics can conflict meaningfully for now
            seen_labels: dict[str, list[dict[str, Any]]] = {}
            for n in type_nodes:
                normalized = n["label"].lower().strip()
                seen_labels.setdefault(normalized, []).append(n)

            for label, group in seen_labels.items():
                if len(group) < 2:
                    continue
                # Sort by confirmed_at, keep freshest
                group.sort(key=lambda n: n.get("last_confirmed_at", ""), reverse=True)
                winner = group[0]
                for loser in group[1:]:
                    conflicts.append({
                        "type": "conflict",
                        "node_type": node_type,
                        "label": label,
                        "winner_id": winner["id"],
                        "loser_id": loser["id"],
                        "action": "archive_loser",
                        "reason": f"Stale fact replaced by fresher evidence",
                    })
                    loser["is_archived"] = True
                    loser["archived_at"] = datetime.now(timezone.utc).isoformat()

        # Persist changes
        self._write_jsonl(f"{expert_id}_nodes", nodes)
        return conflicts

    async def stale_detection(self, expert_id: str, max_age_days: int = 60) -> list[dict[str, Any]]:
        """Find edges and nodes not confirmed recently."""
        edges = self._read_jsonl(f"{expert_id}_edges")
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        stale = []

        for edge in edges:
            if edge.get("is_tombstone"):
                continue
            confirmed = edge.get("last_confirmed_at", "")
            try:
                confirmed_dt = datetime.fromisoformat(confirmed.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if confirmed_dt < cutoff:
                stale.append({
                    "type": "stale_edge",
                    "edge_id": edge["id"],
                    "from": edge["from_node_id"],
                    "to": edge["to_node_id"],
                    "relation": edge["relation"],
                    "last_confirmed": confirmed,
                })

        self._write_jsonl(f"{expert_id}_edges", edges)
        return stale

    async def gap_hunt(self, expert_id: str) -> list[dict[str, Any]]:
        """Find unconnected node clusters and suggest connections."""
        nodes = self._read_jsonl(f"{expert_id}_nodes")
        edges = self._read_jsonl(f"{expert_id}_edges")

        connected_ids: set[str] = set()
        for e in edges:
            if not e.get("is_tombstone"):
                connected_ids.add(e["from_node_id"])
                connected_ids.add(e["to_node_id"])

        isolated = [n for n in nodes if n["id"] not in connected_ids and not n.get("is_archived")]

        gaps = []
        for n in isolated:
            gaps.append({
                "type": "gap",
                "node_id": n["id"],
                "node_type": n["node_type"],
                "label": n["label"],
                "suggestion": f"Connect {n['node_type']} '{n['label']}' to related topics or metrics",
            })

        return gaps

    async def graph_pruning(self, expert_id: str, tombstone_age_days: int = 30) -> int:
        """Remove old tombstoned edges."""
        edges = self._read_jsonl(f"{expert_id}_edges")
        cutoff = datetime.now(timezone.utc) - timedelta(days=tombstone_age_days)
        pruned = 0
        kept = []

        for edge in edges:
            if edge.get("is_tombstone"):
                tombstoned = edge.get("tombstoned_at", "")
                try:
                    ts_dt = datetime.fromisoformat(tombstoned.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    kept.append(edge)
                    continue
                if ts_dt < cutoff:
                    pruned += 1
                    continue
            kept.append(edge)

        self._write_jsonl(f"{expert_id}_edges", kept)
        return pruned

    async def self_reflection(self, expert_id: str) -> dict[str, Any]:
        """Analyze quality of memory operations and detect issues."""
        runs = self._read_jsonl(expert_id)
        nodes = self._read_jsonl(f"{expert_id}_nodes")
        edges = self._read_jsonl(f"{expert_id}_edges")

        total_runs = len(runs)
        total_nodes = len(nodes)
        total_edges = len(edges)
        archived_nodes = sum(1 for n in nodes if n.get("is_archived"))
        tombstoned_edges = sum(1 for e in edges if e.get("is_tombstone"))

        # Confidence audit
        low_confidence_nodes = [n for n in nodes if n.get("confidence", 0) < 0.4 and not n.get("is_archived")]

        # Find missed patterns: nodes of same type with similar labels but no edge
        topic_nodes = [n for n in nodes if n["node_type"] == "topic" and not n.get("is_archived")]
        missing_links = 0
        for i, n1 in enumerate(topic_nodes):
            for n2 in topic_nodes[i + 1:]:
                connected = any(
                    (e["from_node_id"] == n1["id"] and e["to_node_id"] == n2["id"]) or
                    (e["from_node_id"] == n2["id"] and e["to_node_id"] == n1["id"])
                    for e in edges if not e.get("is_tombstone")
                )
                if not connected:
                    missing_links += 1

        return {
            "expert_id": expert_id,
            "total_runs": total_runs,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "archived_nodes": archived_nodes,
            "tombstoned_edges": tombstoned_edges,
            "low_confidence_nodes": len(low_confidence_nodes),
            "missing_topic_links": missing_links,
            "health": "good" if total_runs > 0 and total_nodes > 0 else "insufficient_data",
            "reflected_at": datetime.now(timezone.utc).isoformat(),
        }

    async def run_housekeeping(self, expert_id: str) -> dict[str, Any]:
        """Run all housekeeping tasks and return a report.

        Runs: conflict_scan, stale_detection, gap_hunt, graph_pruning, self_reflection.
        Returns structured report suitable for logging and skill auto-update.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        conflicts = await self.conflict_scan(expert_id)
        stale_edges = await self.stale_detection(expert_id)
        gaps = await self.gap_hunt(expert_id)
        pruned = await self.graph_pruning(expert_id)
        reflection = await self.self_reflection(expert_id)

        return {
            "expert_id": expert_id,
            "conflicts": conflicts,
            "stale_edges": stale_edges,
            "gaps": gaps,
            "pruned_edges": pruned,
            "reflection": reflection,
            "timestamp": timestamp,
        }

    # ── Skill Auto-Update (Phase 8) ─────────────────────────

    async def suggest_skill_updates(
        self,
        expert_id: str,
        min_runs: int = 5,
        min_score: int | None = None,
        max_score: int | None = None,
    ) -> list[dict[str, Any]]:
        """Analyze run history and suggest skill changes.

        Detects patterns:
        - High-scoring topics → suggest promoting in skill prompts
        - Low-scoring topics → suggest avoiding/deprioritizing
        - Platform-specific performance differences

        Returns list of structured suggestions for apply_skill_update().
        """
        runs = self._read_jsonl(expert_id)
        if len(runs) < min_runs:
            return []

        # Group by topic
        topic_groups: dict[str, list[dict[str, Any]]] = {}
        for r in runs:
            t = r.get("topic", "").lower().strip()
            if r.get("draft") and len(r["draft"]) > 20:  # skip content-only entries
                continue
            if not t:
                continue
            topic_groups.setdefault(t, []).append(r)

        suggestions: list[dict[str, Any]] = []

        for topic, group in topic_groups.items():
            if len(group) < 3:
                continue

            # Extract scores
            scores: list[float] = []
            for r in group:
                s = r.get("final_score") or (r.get("score") or {}).get("overall")
                try:
                    s = float(s) if s is not None else 0
                except (TypeError, ValueError):
                    s = 0
                scores.append(s)

            avg = sum(scores) / len(scores)
            hit_count = len(group)

            # Platform breakdown
            platforms = Counter(r.get("platform", "telegram") for r in group)

            # High performers
            if (min_score is not None and avg >= min_score) or (min_score is None and avg >= 80):
                high_hits = sum(1 for s in scores if s >= 80)
                if high_hits >= 3:
                    suggestions.append({
                        "topic": topic,
                        "avg_score": round(avg, 1),
                        "hit_count": high_hits,
                        "total_runs": hit_count,
                        "platforms": dict(platforms.most_common()),
                        "suggested_action": "promote",
                        "rationale": f"Topic '{topic}' averages {avg:.0f}/100 across {high_hits} runs — promote in skill prompts",
                        "target_agent": "strategist",
                        "target_skill": "hook_generation",
                        "weight": f"+{min(25, int((avg - 70) / 2))}%",
                    })

            # Low performers
            if (max_score is not None and avg <= max_score) or (max_score is None and avg <= 50):
                low_hits = sum(1 for s in scores if s <= 50)
                if low_hits >= 3:
                    suggestions.append({
                        "topic": topic,
                        "avg_score": round(avg, 1),
                        "hit_count": low_hits,
                        "total_runs": hit_count,
                        "platforms": dict(platforms.most_common()),
                        "suggested_action": "avoid",
                        "rationale": f"Topic '{topic}' averages {avg:.0f}/100 across {low_hits} low runs — deprioritize or add guardrails",
                        "target_agent": "strategist",
                        "target_skill": "hook_generation",
                        "weight": f"-{min(25, int((50 - avg) / 2))}%",
                    })

            # Platform-specific
            if len(platforms) >= 2:
                for plat in platforms:
                    plat_runs = [r for r in group if r.get("platform") == plat]
                    plat_scores = []
                    for r in plat_runs:
                        s = r.get("final_score") or (r.get("score") or {}).get("overall")
                        try:
                            s = float(s) if s is not None else 0
                        except (TypeError, ValueError):
                            s = 0
                        plat_scores.append(s)
                    if len(plat_runs) >= 3:
                        plat_avg = sum(plat_scores) / len(plat_scores)
                        if plat_avg >= 80:
                            suggestions.append({
                                "topic": topic,
                                "platform": plat,
                                "avg_score": round(plat_avg, 1),
                                "hit_count": sum(1 for s in plat_scores if s >= 80),
                                "suggested_action": "promote",
                                "rationale": f"Platform {plat} performs well (avg {plat_avg:.0f}) for topic '{topic}'",
                                "target_skill": "platform_optimization",
                                "weight": "+10%",
                            })

        return suggestions

    async def apply_skill_update(
        self,
        skill_registry: Any,  # SkillRegistry
        agent_name: str,
        skill_name: str,
        update: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply a suggested update to a SKILL.md file.

        Updates learned_patterns and evolution_log, increments version.
        """
        try:
            skill = skill_registry.get(agent_name, skill_name)
        except KeyError:
            return {"status": "error", "reason": f"Skill '{skill_name}' not found for agent '{agent_name}'"}

        from .skill_loader import Skill

        skill_path = skill.path
        current = Skill(skill_path)

        # Prepare new pattern entry
        new_pattern = {
            "pattern": update.get("pattern", update.get("topic", "")),
            "avg_score": update.get("avg_score", 0),
            "used": update.get("hit_count", 0),
            "weight": update.get("weight", "0%"),
        }

        # Merge learned patterns
        patterns = list(current.learned_patterns or [])
        patterns.append(new_pattern)

        # Evolution log entry
        log_entry = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "change": f"added pattern: {new_pattern['pattern']}",
            "source": update.get("source", "memory.suggest_skill_updates"),
        }
        evolution = list(current.evolution_log or [])
        evolution.append(log_entry)

        new_version = current.version + 1

        # Build updated SKILL.md content
        new_content = self._build_skill_md(
            frontmatter={
                "skill": skill_name,
                "version": new_version,
                "agent": agent_name,
                "category": current.category,
            },
            base_prompt=current.base_prompt,
            learned_patterns=patterns,
            evolution_log=evolution,
        )

        skill_path.write_text(new_content, encoding="utf-8")
        logger.info(
            "Applied update to %s/%s: version %d→%d, pattern=%s",
            agent_name, skill_name, current.version, new_version, new_pattern["pattern"][:50],
        )

        return {
            "status": "applied",
            "skill": skill_name,
            "version": new_version,
            "pattern_added": new_pattern["pattern"],
            "patterns_total": len(patterns),
            "evolution_entries": len(evolution),
        }

    @staticmethod
    def _build_skill_md(
        frontmatter: dict[str, Any],
        base_prompt: str,
        learned_patterns: list[dict[str, Any]],
        evolution_log: list[dict[str, Any]],
    ) -> str:
        """Build a SKILL.md file from components."""
        import yaml as _yaml

        fm = _yaml.dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
        patterns_yaml = _yaml.dump(learned_patterns, allow_unicode=True, sort_keys=False).strip()
        evolution_yaml = _yaml.dump(evolution_log, allow_unicode=True, sort_keys=False).strip()

        return (
            f"---\n{fm}\n---\n\n"
            f"## Base Prompt\n{base_prompt.strip()}\n\n"
            f"## Learned Patterns\n{patterns_yaml}\n\n"
            f"## Evolution Log\n{evolution_yaml}\n"
        )

    # ── Internal helpers ────────────────────────────────────

    def _append_jsonl(self, expert_id: str, data: dict[str, Any]) -> None:
        file_path = self.data_dir / f"{expert_id}.jsonl"
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def _read_jsonl(self, expert_id: str) -> list[dict[str, Any]]:
        file_path = self.data_dir / f"{expert_id}.jsonl"
        if not file_path.exists():
            return []
        results = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return results

    def _write_jsonl(self, expert_id: str, data: list[dict[str, Any]]) -> None:
        file_path = self.data_dir / f"{expert_id}.jsonl"
        with open(file_path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
