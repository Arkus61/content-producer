import asyncio
import os
from pathlib import Path
from .expert_card.card import ExpertCard
from .interviewer.session import InterviewSession
from .interviewer.analyzer import analyze_interview
from .producer_agent.planner import generate_content_plan
from .expert_card.parser import save_card
from .transcriber.pipeline import transcribe
from .transcriber.youtube import is_youtube_url

async def run_interview():
    """Classic text-based interview."""
    name = input("\U0001f399\ufe0f    Как вас зовут? ")
    session = InterviewSession(expert_name=name)
    print("\n\U0001f399\ufe0f    Начинаем интервью!\n")
    
    while not session.is_complete:
        q = session.get_next_question()
        if not q:
            break
        print(f"\n{q.text}")
        answer = input("> ")
        session.add_response(q.id, answer)
        p = session.get_progress()
        print(f"\U0001f4ca   Прогресс: {p['progress_percent']}%")
    
    print("\n\u2705    Интервью завершено! Анализирую...")
    return session

async def run_transcription():
    """Transcribe audio/video file or YouTube URL."""
    print("\n\U0001f3a5    Транскрибция аудио/видео")
    source_type = input("Тип источника (1=file, 2=youtube): ")
    name = input("Имя эксперта: ")
    
    if source_type == "1":
        filepath = input("Путь к файлу: ")
        text = await transcribe(filepath, "file", os.environ["OPENAI_API_KEY"])
    else:
        url = input("YouTube URL: ")
        text = await transcribe(url, "youtube", os.environ["OPENAI_API_KEY"])
    
    print(f"\n\u2705    Транскрибируемый текст ({len(text)} символов):")
    print(text[:1000])
    return text, name

async def main():
    print("\n\U0001f3ac   Content Producer\n")
    print("1. Текстовое интервью")
    print("2. Транскрибация аудио/видео")
    choice = input("\nВыбор (1/2): ")
    
    if choice == "2":
        text, name = await run_transcription()
    else:
        session = await run_interview()
    
    print("\n\u2705    Анализ и создание карточки...")
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("\u274c    OPENAI_API_KEY не установлен!")
        return
    
    # Create session with collected data
    session = InterviewSession(expert_name=name)
    session.add_response("main_input", text if choice == "2" else "\n".join(session.responses.values()))
    session.is_complete = True
    
    card = await analyze_interview(session, api_key)
    
    experts_dir = Path("experts")
    experts_dir.mkdir(exist_ok=True)
    save_path = experts_dir / f"{name.lower().replace(' ', '_')}.md"
    save_card(card, save_path)
    print(f"\n\U0001f4c4    Карточка сохранена: {save_path}")
    
    plan = generate_content_plan(card)
    print("\n\U0001f4c5   Контент-план на неделю:")
    for item in plan:
        print(f"  [{item['day']}] {item['pillar']}: {item['topic']}")

if __name__ == "__main__":
    asyncio.run(main())
