# Deployment

## Docker (Recommended)

```bash
# Copy env file
cp .env.example .env
# Edit .env with your OPENAI_API_KEY

# Start
docker compose up -d --build

# View logs
docker compose logs -f app

# Stop
docker compose down
```

## Docker Compose with PostgreSQL

```bash
OPENAI_API_KEY=sk-... docker compose up -d
```

## Manual

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

## Environment Variables

| Variable | Description | Default |
|----------|------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required for AI) | "" |
| `DATABASE_URL` | SQLAlchemy connection string | sqlite db |
| `DEBUG` | Enable debug logging | false |
| `CORS_ORIGINS` | Allowed origins (comma-sep) | * |
