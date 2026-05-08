import json
import openai
from .session import InterviewSession
from .questions import QUESTION_BANK
from ..expert_card.card import (
    ExpertCard, ToneOfVoice, Audience, ContentStrategy,
    PersonalityProfile, ExpertiseProfile, ProductProfile,
)
from ..ai.prompts import INTERVIEW_ANALYZER_SYSTEM


async def analyze_interview(session: InterviewSession, api_key: str) -> ExpertCard:
    """Analyze interview responses and produce a full ExpertCard.

    Works with any subset of the 300 questions — extracts what's available.
    """
    client = openai.AsyncOpenAI(api_key=api_key)

    # Group responses by block for context
    blocks_text = {}
    for block in ["personality", "expertise", "product"]:
        block_responses = session.get_block_responses(block)
        if block_responses:
            block_q = {q.id: q.text for q in QUESTION_BANK if q.block == block}
            section = []
            for q_id, answer in block_responses.items():
                q_text = block_q.get(q_id, q_id)
                section.append(f"Q: {q_text}\nA: {answer}")
            blocks_text[block] = "\n\n".join(section)

    # Build context for the AI
    context_parts = []
    if "personality" in blocks_text:
        context_parts.append(f"=== РАСПАКОВКА ЛИЧНОСТИ ===\n{blocks_text['personality']}")
    if "expertise" in blocks_text:
        context_parts.append(f"=== РАСПАКОВКА ЭКСПЕРТНОСТИ ===\n{blocks_text['expertise']}")
    if "product" in blocks_text:
        context_parts.append(f"=== РАСПАКОВКА ПРОДУКТА ===\n{blocks_text['product']}")

    full_context = "\n\n".join(context_parts)

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": INTERVIEW_ANALYZER_SYSTEM},
            {"role": "user", "content": f"Ответы эксперта:\n{full_context}"},
        ],
        response_format={"type": "json_object"},
    )

    data = json.loads(response.choices[0].message.content)

    # Parse personality profile
    p_data = data.get("personality", {})
    personality = PersonalityProfile(
        values=p_data.get("values", []),
        traits=p_data.get("traits", []),
        hobbies=p_data.get("hobbies", []),
        lifestyle=p_data.get("lifestyle", ""),
        family_background=p_data.get("family_background", ""),
        philosophy=p_data.get("philosophy", ""),
        inspirations=p_data.get("inspirations", []),
        fun_facts=p_data.get("fun_facts", []),
        favorite_quote=p_data.get("favorite_quote", ""),
        childhood_dream=p_data.get("childhood_dream", ""),
        proud_of=p_data.get("proud_of", ""),
        communication_style=p_data.get("communication_style", ""),
    )

    # Parse expertise profile
    ep_data = data.get("expertise_profile", {})
    expertise_profile = ExpertiseProfile(
        definition=ep_data.get("definition", ""),
        unique_skills=ep_data.get("unique_skills", []),
        journey=ep_data.get("journey", ""),
        growth_phases=ep_data.get("growth_phases", []),
        mistakes=ep_data.get("mistakes", []),
        hacks=ep_data.get("hacks", []),
        risks=ep_data.get("risks", []),
        market_trends=ep_data.get("market_trends", []),
        competitors=ep_data.get("competitors", []),
        competitive_advantage=ep_data.get("competitive_advantage", ""),
        mission=ep_data.get("mission", ""),
        method=ep_data.get("method", ""),
        achievements=ep_data.get("achievements", []),
        metrics=ep_data.get("metrics", ""),
        ideal_day=ep_data.get("ideal_day", ""),
        sources=ep_data.get("sources", []),
        beliefs=ep_data.get("beliefs", []),
        client_loves=ep_data.get("client_loves", []),
        client_dislikes=ep_data.get("client_dislikes", []),
    )

    # Parse product profile
    pr_data = data.get("product", {})
    product = ProductProfile(
        name=pr_data.get("name", ""),
        description=pr_data.get("description", ""),
        problem=pr_data.get("problem", ""),
        differentiator=pr_data.get("differentiator", ""),
        origin_story=pr_data.get("origin_story", ""),
        production_process=pr_data.get("production_process", []),
        quality_standards=pr_data.get("quality_standards", []),
        ideal_client=pr_data.get("ideal_client", ""),
        client_journey=pr_data.get("client_journey", []),
        common_objections=pr_data.get("common_objections", []),
        unique_advantages=pr_data.get("unique_advantages", []),
        secrets=pr_data.get("secrets", []),
        guarantees=pr_data.get("guarantees", ""),
        pricing=pr_data.get("pricing", ""),
        loyalty_program=pr_data.get("loyalty_program", ""),
        certifications=pr_data.get("certifications", []),
        failed_cases=pr_data.get("failed_cases", []),
        future_plans=pr_data.get("future_plans", []),
    )

    # Parse tone
    tone_data = data.get("tone", {})
    tone = ToneOfVoice(
        style=tone_data.get("style", "expert"),
        catchphrases=tone_data.get("catchphrases", []),
        emoji_style=tone_data.get("emoji_style", "moderate"),
    )

    # Parse audience
    aud_data = data.get("audience", {})
    audience = Audience(
        demographics=aud_data.get("demographics", ""),
        pain_points=aud_data.get("pain_points", []),
        core_segment=aud_data.get("core_segment", ""),
        mass_segment=aud_data.get("mass_segment", ""),
    )

    return ExpertCard(
        name=data.get("name", session.expert_name or "Unknown"),
        profession=data.get("profession", ""),
        city=data.get("city", ""),
        personality=personality,
        expertise_profile=expertise_profile,
        product=product,
        expertise=ep_data.get("unique_skills", []),
        uvp=data.get("uvp", ""),
        tone=tone,
        audience=audience,
        strategy=ContentStrategy(goals=data.get("content_goals", [])),
        stories=data.get("stories", []),
    )
