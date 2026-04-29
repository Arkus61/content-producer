import asyncio
import os
import sys
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from expert_card.card import ExpertCard
from interviewer.session import InterviewSession
from interviewer.questions import SESSIONS, BLOCKS, SUBBLOCKS, get_questions_for_session
from interviewer.analyzer import analyze_interview
from producer_agent.planner import generate_content_plan
from expert_card.parser import save_card
from transcriber.pipeline import transcribe
from transcriber.youtube import is_youtube_url


SESSION_LABELS = {
    "session_1": "Сессия 1: Личность (хобби, ценности, семья) — 45 вопросов",
    "session_2": "Сессия 2: Личность + старт экспертности — 55 вопросов",
    "session_3": "Сессия 3: Экспертность (основная часть) — 65 вопросов",
    "session_4": "Сессия 4: Экспертность + старт продукта — 80 вопросов",
    "session_5": "Сессия 5: Продукт (детально) — 55 вопросов",
}


def choose_session() -> str:
    """Let user pick a session or do the full interview."""
    print("\n📋 Выберите формат интервью:\n")
    print("  0. Полное интервью (300 вопросов, ~4-5 часов)")
    for i, (key, label) in enumerate(SESSION_LABELS.items(), 1):
        q_count = len(get_questions_for_session(key))
        print(f"  {i}. {label} ({q_count} вопросов)")

    print()
    choice = input("Выбор (0-5): ").strip()

    if choice == "0":
        return ""  # full interview
    elif choice in ("1", "2", "3", "4", "5"):
        return f"session_{choice}"
    else:
        print(f"Неизвестный выбор: {choice}, запускаю полное интервью")
        return ""


async def run_interview(session_name: str = "") -> dict:
    """Run text-based interview with optional session restriction."""
    name = input("Как вас зовут? ")
    session = InterviewSession(expert_name=name, session_name=session_name)

    if session_name:
        label = SESSION_LABELS.get(session_name, session_name)
        total = len(get_questions_for_session(session_name))
        print(f"\n🎬 Начинаем: {label}")
        print(f"   Всего вопросов: {total}\n")
    else:
        print("\n🎬 Начинаем полное интервью (300 вопросов)!")
        print("   Рекомендуется разбить на 5 сессий по 60-90 минут.\n")

    while not session.is_complete:
        q = session.get_next_question()
        if not q:
            break

        # Show block/subblock context
        progress = session.get_progress()
        block_emoji = {"personality": "🧑", "expertise": "💡", "product": "📦"}.get(q.block, "❓")
        print(f"\n{block_emoji} [{progress['answered']+1}/{progress['total']}] ({q.block}/{q.subblock})")
        print(f"   {q.text}")

        answer = input("   > ")
        if answer.lower() in ("quit", "exit", "выход"):
            print("Завершаю интервью...")
            break

        session.add_response(q.id, answer)

        # Show progress every 10 questions
        if progress['answered'] % 10 == 9:
            p = session.get_progress()
            print(f"\n   📊 Прогресс: {p['progress_percent']}% ({p['answered']}/{p['total']})")
            for block, stats in p['blocks'].items():
                if stats['answered'] > 0:
                    print(f"      {block}: {stats['answered']}/{stats['total']} ({stats['percent']}%)")

    # Final progress
    p = session.get_progress()
    print(f"\n✅ Интервью завершено! Отвечено: {p['answered']}/{p['total']} ({p['progress_percent']}%)")
    for block, stats in p['blocks'].items():
        if stats['answered'] > 0:
            emoji = {"personality": "🧑", "expertise": "💡", "product": "📦"}.get(block, "")
            print(f"   {emoji} {block}: {stats['answered']}/{stats['total']} ({stats['percent']}%)")

    all_text = "\n".join(session.responses.values())
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
    print("╔══════════════════════════════════════════╗")
    print("║       Content Producer v2.0              ║")
    print("║   Распаковка эксперта: 300 вопросов      ║")
    print("╚══════════════════════════════════════════╝")
    print()
    print("1. Текстовое интервью")
    print("2. Транскрибация аудио/видео")
    choice = input("\nВыбор (1/2): ").strip()

    if choice == "2":
        result = await run_transcription()
    elif choice == "1":
        session_name = choose_session()
        result = await run_interview(session_name)
    else:
        print(f"Неизвестный выбор: {choice}")
        sys.exit(1)

    text = result["text"]
    name = result["name"]

    print("\nАнализ и создание карточки...")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("OPENAI_API_KEY not set!")
        return

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
    print("\nКонтент-план на неделю:")
    for item in plan:
        print(f"  [{item['day']}] {item['pillar']}: {item['topic']}")


if __name__ == "__main__":
    asyncio.run(main())
