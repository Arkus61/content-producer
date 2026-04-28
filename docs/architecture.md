# Architecture

## Overview

Content Producer is an AI-powered SaaS that helps experts and bloggers create content through:

1. **Interview** → AI conducts a structured interview, unpacks personality
2. **Expert Card** → Creates a structured profile (name, voice, expertise, audience)
3. **Producer Agent** → Develops content strategy and generates posts/scripts

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Content Producer SaaS                    │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐   ┌──────────────┐   ┌─────────────┐         │
│  │Interview │──▶│ Expert Card  │──▶│ Producer     │         │
│  │Module    │   │ (.md/JSON)   │   │ Agent       │         │
│  └──────────┘   └──────────────┘   └──────┬──────┘         │
│                                           │                │
│                                   ┌───────▼────────┐       │
│                                   │ Content        │       │
│                                   │ Generator      │       │
│                                   │ (posts+scripts)│       │
│                                   └────────────────┘       │
│                                                             │
│  PostgreSQL (experts, sessions, content)                   │
│  FastAPI (REST API)                                        │
│  OpenAI API (embeddings, GPT-4o, Whisper)                  │
└─────────────────────────────────────────────────────────────┘
```

## Module Dependencies

```
api ─┬─▶ interviewer/
     ├─▶ expert_card/
     ├─▶ producer_agent/
     ├─▶ content_generator/
     ├─▶ transcriber/
     └─▶ db/

producer_agent ──▶ expert_card
content_generator ──▶ expert_card
transcriber ──▶ whisper (OpenAI API)
```

## Data Flow

1. Expert starts interview → `POST /api/interview/start`
2. Answers questions → `POST /api/interview/{id}/answer`
3. Interview finalizes → `POST /api/interview/{id}/finalize`
4. AI creates Expert Card → stored in DB + saved as .md
5. Generate content → `POST /api/experts/{id}/content`
6. Get content plan → `POST /api/experts/{id}/plan`

## Transcription Pipeline

```
YouTube URL ──▶ yt-dlp ──▶ .wav ──▶ Whisper API ──▶ text
Audio file  ──▶ ffmpeg ──▶ .wav ──▶ Whisper API ──▶ text
Video file  ──▶ ffmpeg ──▶ .wav ──▶ Whisper API ──▶ text
```

Generated text flows through the same analyzer pipeline → Expert Card.
