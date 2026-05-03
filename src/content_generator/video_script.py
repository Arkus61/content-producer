from __future__ import annotations

import json
import re

from ..expert_card.card import ExpertCard
from ..content_pipeline import ContentPipeline


def _sanitize_topic(topic: str) -> str:
    topic = topic.strip()
    topic = "".join(ch for ch in topic if ch == "\n" or ord(ch) >= 32)
    topic = re.sub(r"[`\x00-\x1f]", "", topic)
    return f"```\n{topic}\n```"


async def generate_video_script(
    card: ExpertCard,
    topic: str,
    duration_minutes: int = 5,
    api_key: str = "",
) -> dict:
    """Generate a video script via the full agent chain."""
    pipeline = ContentPipeline(api_key=api_key)
    result = await pipeline.run(
        card=card,
        topic=topic,
        platform="video",
        content_type="video_script",
    )
    # Attempt to parse the content back into the JSON fields expected by existing API
    content = result.get("content", "")
    visual = result.get("visual_brief", {})

    # Extract hook/intro/body/cta from the draft using simple split
    script = {
        "hook": "",
        "intro": "",
        "body": [],
        "cta": "",
        "b_roll_suggestions": visual.get("b_roll", []),
        "visual_brief": visual,
        "pipeline_result": result,
    }

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if lines:
        script["hook"] = lines[0]
    if len(lines) > 1:
        script["intro"] = lines[1]
    if len(lines) > 2:
        script["cta"] = lines[-1]
    if len(lines) > 3:
        script["body"] = lines[2:-1]

    return script
