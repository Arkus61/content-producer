# API Documentation

Base URL: `http://localhost:8000`

## Health

```
GET /health
→ {"status": "ok", "version": "0.2.0"}
```

## Interviews

### Start Interview
```
POST /api/interview/start
Body: {"expert_name": "Иван Петров"}
→ {"session_id": "...", "question": "...", "progress": {...}}
```

### Submit Answer
```
POST /api/interview/{session_id}/answer
Body: {"answer": "Я занимаюсь маркетингом 10 лет..."}
→ {"question": "...", "is_complete": false, "progress": {...}}
```

### Finalize Interview
```
POST /api/interview/{session_id}/finalize
→ {"expert_id": "...", "card": {...}, "saved_to": "experts/ivan.md"}
```

## Transcriptions

### YouTube URL
```
POST /api/transcribe/youtube?expert_name=Ivan&youtube_url=https://youtube.com/watch?v=...&language=ru
→ {"transcription_id": "...", "preview": "..."}
```

### Upload File
```
POST /api/transcribe/upload
Form: expert_name=Ivan, file=@video.mp4, language=ru
→ {"transcription_id": "...", "preview": "..."}
```

### Get Transcription
```
GET /api/transcribe/{id}
→ {"id": "...", "text": "полный текст транскрипции", ...}
```

### Transcription → Expert Card
```
POST /api/transcribe/{id}/to-card
→ {"expert_id": "...", "card": {...}}
```

## Experts

### List
```
GET /api/experts?skip=0&limit=50
→ {"experts": [{"id": "...", "name": "...", ...}]}
```

### Get
```
GET /api/experts/{expert_id}
→ {"id": "...", "name": "...", "profession": "...", ...}
```

### Create
```
POST /api/experts
Body: {"name": "...", "profession": "...", "expertise": [...]}
→ {"expert_id": "..."}
```

### Delete
```
DELETE /api/experts/{expert_id}
→ {"deleted": true}
```

## Content

### Generate
```
POST /api/experts/{expert_id}/content
Body: {"topic": "topic", "content_type": "post", "platform": "telegram"}
→ {"content_id": "...", "content": "..."}
```

### Content Plan
```
POST /api/experts/{expert_id}/plan?days=7
→ {"plan": [{"day": "...", "pillar": "...", "topic": "..."}]}
```

### Get Expert Content
```
GET /api/experts/{expert_id}/content?skip=0&limit=20
→ {"items": [...]}
```
