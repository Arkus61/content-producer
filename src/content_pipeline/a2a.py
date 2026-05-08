"""A2A Protocol — Agent-to-Agent communication format."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class A2AMessage:
    """Standard A2A message envelope."""

    def __init__(
        self,
        from_agent: str,
        to_agent: str,
        task_type: str,
        payload: dict[str, Any] | None = None,
        call_id: str | None = None,
    ) -> None:
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.task_type = task_type
        self.payload = payload or {}
        self.call_id = call_id or str(uuid4())
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "call_id": self.call_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> A2AMessage:
        msg = cls(
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            task_type=data["task_type"],
            payload=data.get("payload", {}),
            call_id=data.get("call_id"),
        )
        msg.timestamp = data.get("timestamp", msg.timestamp)
        return msg


class A2AResponse:
    """Standard A2A response envelope."""

    def __init__(
        self,
        from_agent: str,
        to_agent: str,
        call_id: str,
        status: str = "ok",
        payload: dict[str, Any] | None = None,
        next_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.call_id = call_id
        self.status = status
        self.payload = payload or {}
        self.next_agent = next_agent
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "call_id": self.call_id,
            "status": self.status,
            "payload": self.payload,
            "next_agent": self.next_agent,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> A2AResponse:
        return cls(
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            call_id=data["call_id"],
            status=data.get("status", "ok"),
            payload=data.get("payload", {}),
            next_agent=data.get("next_agent"),
            metadata=data.get("metadata", {}),
        )


class A2ATrace:
    """Tracks a full A2A exchange with timing."""

    def __init__(self, trace_id: str | None = None) -> None:
        self.trace_id = trace_id or str(uuid4())
        self.spans: list[dict[str, Any]] = []
        self._start: dict[str, float] = {}

    def start_span(self, from_agent: str, to_agent: str, task_type: str, parent_span_id: str | None = None) -> str:
        span_id = str(uuid4())
        self._start[span_id] = time.monotonic()
        self.spans.append({
            "trace_id": self.trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "task_type": task_type,
            "status": "started",
            "skills_used": [],
            "tokens_prompt": 0,
            "tokens_completion": 0,
            "latency_ms": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        return span_id

    def end_span(self, span_id: str, status: str = "ok", skills_used: list[str] | None = None,
                 tokens_prompt: int = 0, tokens_completion: int = 0, error: str | None = None) -> None:
        for span in self.spans:
            if span["span_id"] == span_id:
                span["status"] = status
                span["finished_at"] = datetime.now(timezone.utc).isoformat()
                span["latency_ms"] = round((time.monotonic() - self._start.pop(span_id, time.monotonic())) * 1000)
                span["skills_used"] = skills_used or []
                span["tokens_prompt"] = tokens_prompt
                span["tokens_completion"] = tokens_completion
                span["error"] = error
                return

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "total_spans": len(self.spans),
            "spans": self.spans,
        }
