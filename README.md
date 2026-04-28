# 🎬 Content Producer

AI-powered SaaS для помощи экспертам и блогерам в создании контента.

## Идея

1. **Интервью** — AI проводит интервью с экспертом, «распаковывает» личность
2. **Карточка эксперта** (.md) — результат: стиль, голос, ценности, экспертиза, аудитории
3. **Агент-продюсер** — на основе карточки разрабатывает контент-стратегию и генерирует контент

## Архитектура

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
│  Interviewer │───▶│ Expert Card  │───▶│ Producer     │───▶│ Content          │
│  (AI Chat)   │    │ (profile.md) │    │ Agent        │    │ Generator        │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────────┘
```

## Структура проекта

```
content-producer/
├── src/
│   ├── interviewer/          # Модуль интервью — распаковка эксперта
│   ├── expert_card/          # Карточка эксперта + парсер
│   ├── producer_agent/       # Агент-продюсер — стратегия и планирование
│   ├── content_generator/    # Генерация контента (сценарии, посты)
│   └── platforms/            # Интеграции с платформами (YouTube, VK, TG)
├── tests/
├── docs/
├── examples/
├── pyproject.toml            # Зависимости + сборка
└── README.md
```

## Стек

- **Backend:** Python + FastAPI
- **AI:** OpenAI API / Anthropic API
- **SaaS:** Stripe для биллинга
- **DB:** PostgreSQL
- **Frontend:** React / Next.js (позже)

## Roadmap

- [ ] **Phase 1:** Interviewer → Expert Card (MVP)
- [ ] **Phase 2:** Producer Agent — контент-стратегия
- [ ] **Phase 3:** Content Generator — сценарии + посты
- [ ] **Phase 4:** SaaS — биллинг, дашборд, интеграции
