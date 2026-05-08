---
skill: brand_alignment
version: 1
agent: editor
category: evaluation
---

# Brand Alignment

## Base Prompt
You check if content aligns with the expert's brand and product.

Brand:
- UVP: {uvp}
- Mission: {mission}
- Product: {product_name} — {product_description}
- Achievements: {achievements}

Content:
{text}

Output JSON:
- aligned: boolean
- score: 0-100
- conflicts: list of brand conflicts
- suggestions: how to better align with brand

## Learned Patterns
[]

## Evolution Log
[]
