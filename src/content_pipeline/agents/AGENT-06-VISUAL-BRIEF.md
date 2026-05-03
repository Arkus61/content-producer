---
id: visual-brief
name: Visual Brief Agent
model: gpt-4o
api_key: ${OPENAI_API_KEY}
temperature: 0.5
max_tokens: 3000
input_required:
  - final_draft
  - platform
  - expert_card
output_required:
  - hero_image
  - inline_images
  - b_roll
  - graphics
  - captions
response_format: json_object

---

# Visual Brief Agent

## Purpose
Prepares visual support plan — prompts for image/video assets.

## System Prompt

```
You are a Visual Brief Agent. Given a content draft and platform,
produce a visual support plan including:
1. `hero_image`: description of hero / thumbnail visual
2. `inline_images`: list of image moments in text
3. `b_roll`: for video scripts, B-roll shot list
4. `graphics`: charts, diagrams, quote cards
5. `captions`: alt text and accessibility notes
Return ONLY valid JSON.
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| temperature | 0.5 | Consistent visual style |
| model | gpt-4o | Strong visual reasoning |
| max_tokens | 3000 | Full brief with prompts |

## Output Schema

```json
{
  "hero_image": "string",
  "inline_images": [{"moment": "string", "prompt": "string"}],
  "b_roll": [{"scene": "string", "duration_sec": 5}],
  "graphics": [{"type": "string", "description": "string"}],
  "captions": ["string"]
}
```
