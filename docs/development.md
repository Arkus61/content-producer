# Development

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-asyncio
```

## Run Tests

```bash
pytest tests/ -v
```

## Run API

```bash
export OPENAI_API_KEY=sk-...
uvicorn src.api:app --reload
# Open http://localhost:8000/docs
```

## Run CLI

```bash
export OPENAI_API_KEY=sk-...
python -m src.main
```

## Project Structure

```
src/
├── ai/              # Centralized AI prompts
├── api.py           # FastAPI application
├── config.py        # Settings
├── content_generator/  # Post + script generation
├── db/              # SQLAlchemy models + engine
├── expert_card/     # Expert profile card
├── interviewer/     # AI interview system
├── main.py          # CLI entry point
├── platforms/       # Platform integrations (future)
├── producer_agent/  # Strategy + planning agent
└── transcriber/     # Audio/video transcription

tests/
docs/
```
