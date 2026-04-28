# 🎬 Content Producer

AI-powered SaaS для помощи экспертам и блогерам в создании контента.

## Как это работает

```
Интервью (AI) ──▶ Карточка Эксперта ──▶ Агент-Продюсер ──▶ Контент
```

1. **Эксперт проходит AI-интервью** (или загружает видео/аудио)
2. **Создаётся карточка** — стиль, голос, экспертиза, аудитория
3. **AI-Продюсер** строит контент-стратегию
4. **Генератор** создаёт посты и сценарии в голосе эксперта

## Быстрый старт

```bash
# Клонировать
git clone https://github.com/Arkus61/content-producer.git
cd content-producer

# Установить зависимости
pip install -r requirements.txt

# Запустить API
export OPENAI_API_KEY=sk-...
uvicorn src.api:app --reload
# → http://localhost:8000/docs

# Или CLI
python -m src.main
```

## Docker

```bash
OPENAI_API_KEY=sk-... docker compose up -d
```

## Документация

- [Архитектура](docs/architecture.md)
- [API](docs/api.md)
- [Деплой](docs/deployment.md)
- [Разработка](docs/development.md)

## API Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/interview/start` | Начать интервью |
| POST | `/api/interview/{id}/answer` | Ответить на вопрос |
| POST | `/api/interview/{id}/finalize` | Завершить → карточка |
| POST | `/api/transcribe/youtube` | YouTube → транскрипция |
| POST | `/api/transcribe/upload` | Файл → транскрипция |
| POST | `/api/transcribe/{id}/to-card` | Транскрипция → карточка |
| POST | `/api/experts/{id}/content` | Сгенерировать контент |
| POST | `/api/experts/{id}/plan` | Контент-план |
| GET | `/api/experts` | Список экспертов |
| GET | `/health` | Проверка здоровья |

## Стек

- **Backend:** Python 3.11 + FastAPI
- **AI:** OpenAI (GPT-4o, Whisper)
- **DB:** PostgreSQL / SQLite
- **Транскрибация:** ffmpeg + yt-dlp + Whisper
- **Деплой:** Docker + docker-compose

## Roadmap

- [x] MVP архитектура
- [x] AI интервью
- [x] Транскрибация аудио/видео
- [x] Эксперт карточки
- [x] AI-продюсер
- [x] Генерация контента
- [x] REST API
- [ ] Веб-интерфейс (Next.js)
- [ ] Интеграции с платформами
- [ ] Stripe биллинг
- [ ] Мультиязычность
