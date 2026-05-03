"""Agent classes for the content generation pipeline.

Each agent:
- Receives expert_card (style profile included)
- Receives context dict from previous agents
- Returns structured output (dict or str)
- Uses openai AsyncOpenAI client
"""
import json
import logging
from typing import Any

import openai

from ..expert_card.card import ExpertCard

logger = logging.getLogger("content-producer")


def _style_prompt_block(card: ExpertCard) -> str:
    """Build a reusable style prompt block from the expert's style profile."""
    style = card.style
    return f"""--- EXPERT STYLE PROFILE ---
Tone of Voice style: {card.tone.style}
Tone format preference: {card.tone.format_pref}
Emoji style (legacy): {card.tone.emoji_style}

Learned Style Profile:
- vocabulary: {', '.join(style.vocabulary) if style.vocabulary else 'not yet learned'}
- sentence_length: {style.sentence_length}
- humor_level: {style.humor_level}/10
- emoji_usage: {style.emoji_usage}
- story_structure: {style.story_structure}
- call_to_action_style: {style.call_to_action_style}
- style_update_count: {style.update_count}

Always adapt your output to match these style markers.
--- END STYLE PROFILE ---"""


class ResearchAgent:
    """Gathers angles, hooks, and facts for a topic."""

    system_prompt = (
        "You are a Research Agent. For the given topic and expert, produce research notes: "
        "angles, compelling hooks, 2-3 relevant facts or statistics, and counter-points. "
        "Output JSON with keys: angles, hooks, facts, counter_points. "
        "Match the expert's sentence_length, humor_level, and vocabulary from their Style Profile."
    )

    async def run(self, card: ExpertCard, context: dict[str, Any]) -> dict:
        topic = context.get("topic", "")
        client: openai.AsyncOpenAI = context["client"]
        prompt = (
            f"{self.system_prompt}\n\n{_style_prompt_block(card)}\n\n"
            f"EXPERT: {card.name}\nPROFESSION: {card.profession}\nTOPIC: {topic}"
        )
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)


class WriterAgent:
    """Drafts the initial post or script."""

    system_prompt = (
        "You are a Writer Agent. Write a first-draft social post in the expert's voice. "
        "Respect their vocabulary, sentence_length, humor_level, emoji_usage, story_structure, and CTA style. "
        "Output JSON with keys: text (string), title (optional)."
    )

    async def run(self, card: ExpertCard, context: dict[str, Any]) -> dict:
        topic = context.get("topic", "")
        platform = context.get("platform", "telegram")
        research = context.get("research", {})
        client: openai.AsyncOpenAI = context["client"]
        prompt = (
            f"{self.system_prompt}\n\n{_style_prompt_block(card)}\n\n"
            f"EXPERT: {card.name}\nPROFESSION: {card.profession}\n"
            f"PLATFORM: {platform}\nTOPIC: {topic}\n"
            f"RESEARCH: {json.dumps(research, ensure_ascii=False)}"
        )
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)


class StyleEnforcerAgent:
    """Tweaks the draft to strictly match the expert's style."""

    system_prompt = (
        "You are a Style Enforcer Agent. Rewrite the draft so it STRICTLY matches the expert's Style Profile. "
        "Adjust vocabulary, sentence length, humor, emojis, story structure, and CTA style to fit. "
        "Output JSON with keys: text (string), changed (bool), notes (string)."
    )

    async def run(self, card: ExpertCard, context: dict[str, Any]) -> dict:
        draft = context.get("draft", {}).get("text", "")
        client: openai.AsyncOpenAI = context["client"]
        prompt = (
            f"{self.system_prompt}\n\n{_style_prompt_block(card)}\n\n"
            f"DRAFT TO REWRITE:\n{draft}"
        )
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)


class EngagementOptimizerAgent:
    """Adds engagement mechanics without breaking voice."""

    system_prompt = (
        "You are an Engagement Optimizer Agent. Add or refine engagement mechanics "
        "(questions, polls, bold take, cliffhanger) while preserving the expert's Style Profile. "
        "Output JSON with keys: text (string), engagement_elements (list[str])."
    )

    async def run(self, card: ExpertCard, context: dict[str, Any]) -> dict:
        text = context.get("styled_text", "")
        client: openai.AsyncOpenAI = context["client"]
        prompt = (
            f"{self.system_prompt}\n\n{_style_prompt_block(card)}\n\n"
            f"TEXT TO OPTIMIZE:\n{text}"
        )
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)


class CriticAgent:
    """Scores the content and provides structured feedback."""

    system_prompt = (
        "You are a Critic Agent. Evaluate the content against the expert's Style Profile. "
        "Output JSON with keys: overall_score (float 0-10), style_match (float 0-10), "
        "engagement (float 0-10), clarity (float 0-10), feedback (list[str])."
    )

    async def run(self, card: ExpertCard, context: dict[str, Any]) -> dict:
        text = context.get("final_text", "")
        client: openai.AsyncOpenAI = context["client"]
        prompt = (
            f"{self.system_prompt}\n\n{_style_prompt_block(card)}\n\n"
            f"CONTENT TO EVALUATE:\n{text}"
        )
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        # Normalize keys
        return {
            "overall_score": float(data.get("overall_score", 0)),
            "style_match": float(data.get("style_match", 0)),
            "engagement": float(data.get("engagement", 0)),
            "clarity": float(data.get("clarity", 0)),
            "feedback": data.get("feedback", []),
        }


class VisualBriefAgent:
    """Generates a visual brief / image prompt for the post."""

    system_prompt = (
        "You are a Visual Brief Agent. Create a short visual prompt and a preview HTML snippet "
        "for the social post, matching the expert's aesthetic (from Style Profile). "
        "Output JSON with keys: visual_prompt (string), preview_html (string)."
    )

    async def run(self, card: ExpertCard, context: dict[str, Any]) -> dict:
        text = context.get("final_text", "")
        client: openai.AsyncOpenAI = context["client"]
        prompt = (
            f"{self.system_prompt}\n\n{_style_prompt_block(card)}\n\n"
            f"POST TEXT:\n{text}"
        )
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
