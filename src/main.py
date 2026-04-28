import asyncio
import os
import sys
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from expert_card.card import ExpertCard
from interviewer.session import InterviewSession
from interviewer.analyzer import analyze_interview
from producer_agent.planner import generate_content_plan
from expert_card.parser import save_card
from transcriber.pipeline import transcribe
from transcriber.youtube import is_youtube_url


async def run_interview() -> dict:
    """Classic text-based interview."""
    name = input("Как вас зовут? ")
    session = InterviewSession(expert_name=name)
    print("
Начинаем интервью!
")
    
    while not session.is_complete:
        q = session.get_next_question()
        if not q:
            break
        print(f"
{q.text}")
        answer = input("> ")
        session.add_response(q.id, answer)
        p = session.get_progress()
        print(f"Прогресс: {p['progress_percent']}%")
    
    print("
Интервью завершено! Анализирую...")
    all_text = "
".join(session.responses.values())
    return {"session": session, "text": all_text, "name": name}


async def run_transcription() -> dict:
    """Transcribe audio/video file or YouTube URL."""
    print("Транскрибация аудио/видео")
    source_type = input("Тип источника (file/youtube): ")
    expert_name = input("Имя эксперта: ")
    
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("OPENAI_API_KEY not set!")
        sys.exit(1)
    
    if source_type == "file":
        filepath = input("Путь к файлу: ")
        text = await transcribe(filepath, "file", api_key)
    elif source_type == "youtube":
        url = input("YouTube URL: ")
        text = await transcribe(url, "youtube", api_key)
    else:
        print(f"Unknown source type: {source_type}")
        sys.exit(1)
    
    print(f"Транскрибированный текст ({len(text)} символов):")
    print(text[:500])
    return {"text": text, "name": expert_name}


async def main():
    print("Content Producer")
    print("1. Текстовое интервью")
    print("2. Транскрибация аудио/видео")
    choice = input("
Выбор (1/2): ").strip()
    
    if choice == "2":
        result = await run_transcription()
    elif choice == "1":
        result = await run_interview()
    else:
        print(f"Неизвестный выбор: {choice}")
        sys.exit(1)
    
    text = result["text"]
    name = result["name"]
    
    print("
Анализ и создание карточки...")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("OPENAI_API_KEY not set!")
        return
    
    # Create session with collected data for analysis
    analysis_session = InterviewSession(expert_name=name)
    analysis_session.add_response("main_input", text)
    analysis_session.is_complete = True
    
    card = await analyze_interview(analysis_session, api_key)
    
    experts_dir = Path("experts")
    experts_dir.mkdir(exist_ok=True)
    save_path = experts_dir / f"{name.lower().replace(' ', '_')}.md"
    save_card(card, save_path)
    print(f"Карточка сохранена: {save_path}")
    
    plan = generate_content_plan(card)
    print("
Контент-план на неделю:")
    for item in plan:
        print(f"  [{item['day']}] {item['pillar']}: {item['topic']}")


if __name__ == "__main__":
    asyncio.run(main())
