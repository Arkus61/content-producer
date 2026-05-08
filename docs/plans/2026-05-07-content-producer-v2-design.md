# Content Producer v2 — Architecture Design

> Status: approved | Date: 2026-05-07

## 1. Overview

Переход от 6 узкоспециализированных агентов к 4 агентам с наборами переиспользуемых скилов. Каждый агент отвечает за смысловую группу задач, может вызывать других агентов, и со временем обучается через Memory-агента.

**4 агента:**
- 🧠 **Стратег** — исследование аудитории, тренды, хуки, контент-план
- ✍️ **Креатор** — написание, стиль, форматирование, платформенная оптимизация
- 🔍 **Редактор** — оценка, критика, визуальные брифинги, финальная сборка
- 🧬 **Memory** — граф знаний, инсайты, обслуживание БЗ, саморефлексия

**Оркестрация:** диспетчерская модель (PipelineDispatcher), не жёсткая цепочка.

---

## 2. Agent Definitions

### 🧠 Стратег — «Понять аудиторию и найти угол»

| Скилы (промпты) | Инструменты |
|---|---|
| `audience_analysis` — портрет аудитории, боли, триггеры | `web_search` — поиск трендов |
| `trend_research` — что вирусится в нише | `competitor_scrape` — анализ конкурентов |
| `hook_generation` — генерация 5-10 хуков под тему | `analytics_query` — данные из прошлых постов |
| `content_planning` — рубрикатор и календарь | `memory_retrieve` — запрос к Memory-агенту |

**На выходе:** `StrategyBrief` — портрет аудитории, 3 ракурса, хуки, что избегать.

### ✍️ Креатор — «Написать в голосе эксперта»

| Скилы (промпты) | Инструменты |
|---|---|
| `draft_writing` — первый драфт | `style_adapter` — подстройка под StyleProfile |
| `tone_matching` — проверка голоса эксперта | `platform_formatter` — форматирование под Telegram/IG/VK и др. |
| `story_structures` — hook-story-lesson, contrarian и др. | `emoji_optimizer` — расстановка эмодзи |
| `platform_optimization` — адаптация под площадку | `memory_retrieve` — запрос к Memory |

**На выходе:** `Draft` + метаданные (структура, CTA, хештеги).

### 🔍 Редактор — «Оценить и упаковать»

| Скилы (промпты) | Инструменты |
|---|---|
| `multi_dimension_scoring` — 10-мерная оценка | `score_calculator` — weighted average |
| `style_check` — проверка на соответствие бренду | `visual_brief_gen` — промпты для изображений |
| `brand_alignment` — не противоречит ли УТП | `engagement_predictor` — прогноз ER |
| `visual_brief` — что нужно к посту визуально | `final_assembler` — сборка publish-ready пакета |
| `final_review` — финальное решение publish/reject | `memory_ingest` — отправка результатов в Memory |
| `feedback_to_creator` — ревью для доработки | |

**На выходе:** `Scorecard` + `PublishPackage` (текст, визуал, метаданные).

### 🧬 Memory-агент — «Помнить, связывать, улучшать»

Не участвует в генерации напрямую. Обслуживает остальных.

| Скилы | Инструменты | Триггер |
|---|---|---|
| `ingest_run` — сохранить результат прогона | `pgvector` (Supabase) + JSON file cache | После каждого прогона |
| `extract_insights` — извлечь паттерны | `pattern_detector` — кластеризация | Периодически или по запросу |
| `connect_facts` — связать инсайты в граф | `graph_linker` — граф знаний | При накоплении данных |
| `retrieve_context` — выдать релевантную историю | `vector_search` + `graph_traverse` | Перед запуском Стратега/Креатора |
| `detect_gaps` — найти пробелы в понимании | `gap_analyzer` | Раз в сутки |
| `conflict_scan` — найти противоречия | `conflict_resolver` | Раз в 6 часов |
| `stale_detection` — устаревшие связи | `staleness_checker` | Раз в сутки |
| `graph_pruning` — удалить мёртвые связи | `tombstone_marker` | Раз в неделю |
| `self_reflection` — анализ качества работы | `meta_analyzer` | Раз в сутки |
| `skill_update` — предложить изменение скила | `skill_patcher` | При обнаружении паттерна |

**Хранилище:** PostgreSQL + pgvector (основное) + JSON-файлы (локальный кеш/бэкап).

---

## 3. Orchestration

### Диспетчер (PipelineDispatcher)

Логика внутри `ContentPipeline`. Принимает задачу, выбирает стартового агента, управляет вызовами.

```
ContentPipeline.run(topic, platform)
    ┌─ Есть свежий research? ─┐
    │   Да → сразу Креатор     │
    │   Нет → запуск Стратега  │
    └──────────────────────────┘
```

### Три паттерна вызовов

**1. Прямой вызов (агент → агент по цепочке)**

Стратег → Креатор → Редактор. Агент в ответе указывает `next_agent`.

**2. Запрос на доработку (Редактор → Креатор)**

Score < threshold → Редактор возвращает Креатору с feedback. Макс 3 итерации.

**3. Боковой запрос (любой агент → любой агент)**

Пример: Креатор → Стратег («дай больше данных по боли аудитории»).

### Выбор скила

Каждый агент получает `task_type` от диспетчера и сам выбирает скил(ы). Один агент может применить несколько скилов последовательно в рамках одного вызова.

### Общая схема

```
                    ┌──────────────┐
                    │  ДИСПЕТЧЕР   │
                    │ (pipeline)   │
                    └──┬───┬───┬──┘
                       │   │   │
         ┌─────────────┘   │   └─────────────┐
         ▼                 ▼                 ▼
   ┌─────────┐       ┌─────────┐       ┌─────────┐
   │ СТРАТЕГ │◄─────►│ КРЕАТОР │◄─────►│РЕДАКТОР │
   └────┬─────┘       └────┬─────┘       └────┬─────┘
        │                   │                   │
        │        ┌──────────┴──────────┐        │
        └────────┤   MEMORY-АГЕНТ     ├────────┘
                 │  (pgvector + JSON) │
                 └────────────────────┘
                        │
                 ┌──────┴──────┐
                 │    СКИЛЫ    │
                 │ (Markdown,  │
                 │  живые)     │
                 └─────────────┘
```

---

## 4. Skill Format

Скилы хранятся в Markdown в подпапке `skills/` каждого агента.

### Пример структуры

```
src/content_pipeline/
├── agents/
│   ├── strategist/
│   │   ├── agent.md           # конфигурация агента
│   │   └── skills/
│   │       ├── audience_analysis.md
│   │       ├── trend_research.md
│   │       ├── hook_generation.md
│   │       └── content_planning.md
│   ├── creator/
│   │   ├── agent.md
│   │   └── skills/
│   │       ├── draft_writing.md
│   │       ├── tone_matching.md
│   │       ├── story_structures.md
│   │       └── platform_optimization.md
│   ├── editor/
│   │   ├── agent.md
│   │   └── skills/
│   │       ├── multi_dimension_scoring.md
│   │       ├── style_check.md
│   │       ├── brand_alignment.md
│   │       ├── visual_brief.md
│   │       └── final_review.md
│   └── memory/
│       ├── agent.md
│       └── skills/
│           ├── ingest_run.md
│           ├── extract_insights.md
│           ├── connect_facts.md
│           ├── retrieve_context.md
│           └── ...
└── pipeline.py
```

### Формат agent.md

```yaml
---
agent: strategist
model: gpt-4o-mini
temperature: 0.7
version: 1
description: "Анализ аудитории, трендов и генерация стратегии контента"
---
```

### Формат SKILL.md (обучающийся)

```markdown
---
skill: hook_generation
version: 3
agent: strategist
category: creative
---

# Hook Generation

## Base Prompt
Ты генерируешь хуки для эксперта {expert_name} в нише {niche}...

## Learned Patterns
- pattern: "денежные хуки (поднял цены, заработал X)"
  avg_er: 4.2
  used: 14
  weight: +15%
- pattern: "технические хуки (микросервисы, архитектура)"
  avg_er: 0.8
  used: 7
  weight: -20%

## Evolution Log
- 2026-05-10: обнаружен паттерн money-hooks | source: memory_agent.insight #47
- 2026-05-03: добавлен запрет на тех-хуки | source: editor.feedback (3 low-score runs)
```

**Runtime поведение:** агент загружает `base_prompt` + применяет `learned_patterns` с их weights, + получает контекст от Memory → формирует финальный промпт для LLM.

---

## 5. Memory Backend

### Основное хранилище
- **PostgreSQL + pgvector** (через Supabase) — embeddings, векторный поиск, граф связей
- **JSON-файлы** — локальный кеш и бэкап (`data/memory/`)

### Структура графа знаний

```json
{
  "nodes": [
    {"id": "n1", "type": "topic", "label": "ценообразование SaaS"},
    {"id": "n2", "type": "audience_pain", "label": "страх переплатить"},
    {"id": "n3", "type": "hook", "label": "я поднял цены в 2 раза"},
    {"id": "n4", "type": "metric", "label": "ER: 4.2%"},
    {"id": "n5", "type": "temporal", "label": "вторник утро"}
  ],
  "edges": [
    {"from": "n1", "to": "n2", "relation": "addresses_pain", "weight": 0.9},
    {"from": "n1", "to": "n3", "relation": "best_hook", "weight": 0.85, "evidence_count": 14},
    {"from": "n3", "to": "n4", "relation": "achieves", "weight": 0.8},
    {"from": "n5", "to": "n4", "relation": "correlates_with", "weight": 0.6}
  ]
}
```

### Таблицы в PostgreSQL

```sql
CREATE TABLE memory_nodes (
    id UUID PRIMARY KEY,
    agent_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    label TEXT NOT NULL,
    embedding VECTOR(1536),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_confirmed_at TIMESTAMPTZ,
    evidence_count INT DEFAULT 1,
    is_archived BOOLEAN DEFAULT false
);

CREATE TABLE memory_edges (
    id UUID PRIMARY KEY,
    from_node_id UUID REFERENCES memory_nodes(id),
    to_node_id UUID REFERENCES memory_nodes(id),
    relation TEXT NOT NULL,
    weight FLOAT DEFAULT 0.5,
    evidence_count INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_confirmed_at TIMESTAMPTZ,
    is_tombstone BOOLEAN DEFAULT false,
    tombstoned_at TIMESTAMPTZ
);

CREATE INDEX ON memory_nodes USING ivfflat (embedding vector_cosine_ops);
```

### Housekeeping schedule

| Задача | Период | Описание |
|---|---|---|
| `conflict_scan` | раз в 6ч | Поиск противоречащих фактов, разрешение по freshness/evidence |
| `stale_detection` | раз в сутки | Поиск связей без подтверждений 60+ дней |
| `gap_hunt` | раз в сутки | Поиск несвязанных кластеров, создание новых связей |
| `graph_pruning` | раз в неделю | Удаление tombstone-связей, архивация устаревших узлов |
| `self_reflection` | раз в сутки | Анализ failed_predictions, missed_insights, confidence_audit |

---

## 6. Agent Communication Protocol (A2A)

Стандартный протокол для общения между агентами.

### Формат запроса

```json
{
  "from_agent": "creator",
  "to_agent": "strategist",
  "call_id": "uuid",
  "task_type": "research_request",
  "payload": {
    "query": "Дай данные по боли аудитории про бюджетирование",
    "context": {
      "expert_id": "...",
      "topic": "ценообразование SaaS"
    }
  },
  "timestamp": "ISO-8601"
}
```

### Формат ответа

```json
{
  "from_agent": "strategist",
  "to_agent": "creator",
  "call_id": "uuid",
  "status": "ok",
  "payload": {
    "data": "...",
    "insights": ["..."]
  },
  "next_agent": null,
  "metadata": {
    "skills_used": ["audience_analysis"],
    "tokens": 1200,
    "latency_ms": 3400
  }
}
```

---

## 7. API Layer Migration

### Существующие эндпоинты → новые

| Старый эндпоинт | Новый |
|---|---|
| `POST /experts/{id}/content` (v1) | Убрать (deprecated) |
| `POST /experts/{id}/content/v2` | Переписать: новый диспетчер |
| `POST /experts/{id}/plan` | Диспетчер с task_type=`content_plan` |
| `POST /transcribe/youtube` | Без изменений |
| `GET /experts/{id}/reflections` | Memory.retrieve_context(expert_id) |

### Новые эндпоинты

```
GET  /api/experts/{id}/memory/insights   — инсайты эксперта из графа знаний
GET  /api/experts/{id}/memory/gaps       — пробелы в знаниях
POST /api/experts/{id}/memory/reflect    — ручной запуск self_reflection
GET  /api/skills                         — список всех скилов с версиями и метриками
GET  /api/skills/{name}/evolution        — история эволюции конкретного скила
```

---

## 8. LLM Configuration

Каждый агент имеет настраиваемую модель в `agent.md`:

```yaml
# agent.md
agent: creator
model: gpt-4o
temperature: 0.75
max_tokens: 4096
```

Глобальный конфиг в `.env` / `config.py`:

```
DEFAULT_MODEL_STRATEGIST=gpt-4o-mini
DEFAULT_MODEL_CREATOR=gpt-4o
DEFAULT_MODEL_EDITOR=gpt-4o
DEFAULT_MODEL_MEMORY=gpt-4o-mini
```

---

## 9. Observability

### Трассировка вызовов

Каждый вызов между агентами логируется:

```json
{
  "trace_id": "uuid",
  "span_id": "uuid",
  "parent_span_id": "uuid",
  "from_agent": "creator",
  "to_agent": "editor",
  "task_type": "submit_for_review",
  "started_at": "ISO-8601",
  "finished_at": "ISO-8601",
  "status": "ok",
  "skills_used": ["draft_writing", "tone_matching"],
  "tokens_prompt": 3400,
  "tokens_completion": 1200,
  "latency_ms": 4500
}
```

### Метрики (на уровне пайплайна)

- `pipeline.duration_ms` — общее время прогона
- `pipeline.iterations` — количество циклов доработки
- `pipeline.score` — финальный overall score
- `agent.{name}.calls` — количество вызовов агента
- `agent.{name}.tokens` — суммарные токены
- `memory.nodes_total` / `memory.edges_total`
- `memory.conflicts_resolved`
- `skill.{name}.version` / `skill.{name}.effectiveness`

### Логи

- `pipeline.log` — основные этапы (запуск, смена агента, завершение)
- `agent.{name}.log` — детальные логи агента
- `memory.log` — операции с графом (ingest, connect, prune, conflict)
- `error.log` — ошибки с трассировкой

---

## 10. Implementation Order

1. **Инфраструктура скилов** — формат SKILL.md, загрузчик, парсер learned_patterns
2. **Memory-агент** — pgvector схема + базовые операции (ingest, retrieve)
3. **A2A + Диспетчер** — протокол общения + PipelineDispatcher
4. **Стратег** — миграция ResearcherAgent + новые скилы
5. **Креатор** — миграция Writer + StyleEnforcer + EngagementOptimizer в одного агента
6. **Редактор** — миграция Critic + VisualBrief, feedback loop
7. **Memory housekeeping** — conflict_scan, stale_detection, gap_hunt, pruning
8. **Memory self_reflection** + skill auto-update
9. **API-слой** — новые эндпоинты, удаление deprecated
10. **Observability** — трассировка, метрики, логи

---

## 11. Out of Scope

- Multi-platform параллельная генерация в одном прогоне
- A/B тестирование контента
- Real-time trend injection (live firehoses)
- Multi-expert collaboration
- Экспертный UI для review/approve скилов (будет API-only)
