"""Tests for A2A protocol."""
from src.content_pipeline.a2a import A2AMessage, A2AResponse, A2ATrace


def test_a2a_message_creation():
    msg = A2AMessage(
        from_agent="creator",
        to_agent="editor",
        task_type="submit_for_review",
        payload={"content": "test draft", "platform": "telegram"},
    )
    d = msg.to_dict()
    assert d["from_agent"] == "creator"
    assert d["to_agent"] == "editor"
    assert d["task_type"] == "submit_for_review"
    assert d["payload"]["content"] == "test draft"
    assert "call_id" in d
    assert "timestamp" in d


def test_a2a_message_roundtrip():
    msg = A2AMessage("a", "b", "test", {"key": "val"}, call_id="call-1")
    json_str = msg.to_json()
    restored = A2AMessage.from_dict(msg.to_dict())
    assert restored.from_agent == "a"
    assert restored.to_agent == "b"
    assert restored.payload == {"key": "val"}
    assert restored.call_id == "call-1"


def test_a2a_response_creation():
    resp = A2AResponse(
        from_agent="editor",
        to_agent="creator",
        call_id="call-1",
        status="ok",
        payload={"score": 85},
        next_agent=None,
        metadata={"skills_used": ["multi_dimension_scoring"], "tokens": 1200},
    )
    d = resp.to_dict()
    assert d["status"] == "ok"
    assert d["next_agent"] is None
    assert d["payload"]["score"] == 85
    assert "timestamp" in d


def test_a2a_response_error():
    resp = A2AResponse("editor", "creator", "call-1", status="error",
                       payload={"error": "style check failed"})
    assert resp.status == "error"


def test_a2a_response_roundtrip():
    resp = A2AResponse("e", "c", "call-x", status="ok",
                       payload={"data": "done"},
                       next_agent="strategist",
                       metadata={"latency_ms": 500})
    restored = A2AResponse.from_dict(resp.to_dict())
    assert restored.next_agent == "strategist"
    assert restored.metadata["latency_ms"] == 500


def test_a2a_trace_spans():
    trace = A2ATrace("trace-1")
    span1 = trace.start_span("strategist", "creator", "research_brief")
    trace.end_span(span1, status="ok", skills_used=["trend_research"], tokens_prompt=500, tokens_completion=200)

    span2 = trace.start_span("creator", "editor", "submit", parent_span_id=span1)
    trace.end_span(span2, status="error", error="timeout")

    result = trace.to_dict()
    assert result["total_spans"] == 2
    assert result["spans"][0]["status"] == "ok"
    assert result["spans"][0]["skills_used"] == ["trend_research"]
    assert result["spans"][1]["status"] == "error"
    assert result["spans"][1]["error"] == "timeout"
