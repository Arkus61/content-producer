import json
import openai
from .session import InterviewSession
from ..expert_card.card import ExpertCard, ToneOfVoice, Audience, ContentStrategy

SYSTEM_PROMPT = """Ты — аналитик, который превращает ответы интервью в структурированную карточку эксперта.
Извлеки из ответов: имя, профессию, экспертизу, стиль общения, цели, аудиторию, истории.
Отвечай ТОЛЬКО валидным JSON по этой схеме:
{
  "name": "...",
  "profession": "...",
  "expertise": ["...", "..."],
  "uvp": "...",
  "tone_style": "...",
  "audience_demographics": "...",
  "audience_pains": ["...", "..."],
  "content_goals": ["...", "..."],
  "stories": ["...", "..."],
  "platforms": ["...", "..."]
}"""

async def analyze_interview(session: InterviewSession, api_key: str) -> ExpertCard:
    client = openai.AsyncOpenAI(api_key=api_key)
    
    responses_text = ""
    for i, q_id in enumerate(session.asked_questions, 1):
        responses_text += f"Q{i}: {session.responses.get(q_id, '')}\n"
    
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Ответы эксперта:\n{responses_text}"},
        ],
        response_format={"type": "json_object"},
    )
    
    data = json.loads(response.choices[0].message.content)
    
    return ExpertCard(
        name=data.get("name", session.expert_name or "Unknown"),
        profession=data.get("profession", ""),
        expertise=data.get("expertise", []),
        uvp=data.get("uvp", ""),
        tone=ToneOfVoice(style=data.get("tone_style", "expert")),
        audience=Audience(
            demographics=data.get("audience_demographics", ""),
            pain_points=data.get("audience_pains", []),
        ),
        strategy=ContentStrategy(goals=data.get("content_goals", [])),
        stories=data.get("stories", []),
    )
