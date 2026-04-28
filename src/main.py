import asyncio
import os
from pathlib import Path
from .expert_card.card import ExpertCard
from .interviewer.session import InterviewSession
from .interviewer.analyzer import analyze_interview
from .producer_agent.planner import generate_content_plan
from .expert_card.parser import save_card

async def main():
    name = input("\U0001f399\ufe0f Как вас зовут? ")
    session = InterviewSession(expert_name=name)
    print("\n\U0001f399\ufe0f Начинаем интервью!\n")
    
    while not session.is_complete:
        q = session.get_next_question()
        if not q:
            break
        print(f"\n{q.text}")
        answer = input("> ")
        session.add_response(q.id, answer)
        p = session.get_progress()
        print(f"\U0001f4ca Прогресс: {p['progress_percent']}%")
    
    print("\n\u2705 Интервью завершено! Анализирую...")
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("\u274c OPENAI_API_KEY не установлен!")
        return
    card = await analyze_interview(session, api_key)
    
    experts_dir = Path("experts")
    experts_dir.mkdir(exist_ok=True)
    save_path = experts_dir / f"{name.lower().replace(' ', '_')}.md"
    save_card(card, save_path)
    print(f"\n\U0001f4c4 Карточка сохранена: {save_path}")
    
    plan = generate_content_plan(card)
    print("\n\U0001f4c5 Контент-план на неделю:")
    for item in plan:
        print(f"  [{item['day']}] {item['pillar']}: {item['topic']}")

if __name__ == "__main__":
    asyncio.run(main())
