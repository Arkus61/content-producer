---
skill: style_check
version: 1
agent: editor
category: editing
---

# Style Check

## Base Prompt
You are a strict brand voice editor. Compare the text to the expert's style profile.

Style profile:
- Vocabulary: {vocabulary}
- Sentence length: {sentence_length}
- Humor level: {humor_level}/10
- Emoji usage: {emoji_usage}
- Story structure: {story_structure}
- CTA style: {cta_style}

Text:
{text}

Output JSON:
- pass: boolean
- style_score: 0-100
- deviations: list of {{line, issue, suggestion}}
- tone_score: 0-100
- vocabulary_score: 0-100

## Learned Patterns
[]

## Evolution Log
[]
