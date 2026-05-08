---
skill: ingest_run
version: 1
agent: memory
category: storage
---

# Ingest Run

## Base Prompt
Save a completed pipeline run to the knowledge graph.

Extract from run data:
- topic, platform, content_type
- final_score (overall + per-dimension)
- drafts and iterations
- insights from agents
- tokens, latency

Store as nodes and edges:
- Node: run with all metadata
- Edge: run → expert
- Edge: run → topic
- Edge: run → score (if high or low)

## Learned Patterns
[]

## Evolution Log
[]
