---
# Agent Configuration for Content Producer
# Each agent has its own markdown file with YAML frontmatter for settings.
# This is the master registry — all agents are declared here.

agents:
  - id: researcher
    file: AGENT-01-RESEARCHER.md
    class: src.content_pipeline.researcher.ResearcherAgent
  - id: writer
    file: AGENT-02-WRITER.md
    class: src.content_pipeline.writer.WriterAgent
  - id: style-enforcer
    file: AGENT-03-STYLE-ENFORCER.md
    class: src.content_pipeline.style_enforcer.StyleEnforcerAgent
  - id: engagement-optimizer
    file: AGENT-04-ENGAGEMENT-OPTIMIZER.md
    class: src.content_pipeline.engagement_optimizer.EngagementOptimizerAgent
  - id: critic
    file: AGENT-05-CRITIC.md
    class: src.content_pipeline.critic.CriticAgent
  - id: visual-brief
    file: AGENT-06-VISUAL-BRIEF.md
    class: src.content_pipeline.visual_brief.VisualBriefAgent

defaults:
  model: gpt-4o
  temperature: 0.7
  max_tokens: 4096
  reflection_threshold: 80.0
  max_iterations: 3
  api_base: https://api.openai.com/v1

---

# Content Producer — Agent Configuration

This directory contains per-agent configuration files for the 6-agent content pipeline.
Each file uses YAML frontmatter plus markdown body.

## Agent Files

| Agent | File | Purpose |
|-------|------|---------|
| Researcher | `AGENT-01-RESEARCHER.md` | Topic enrichment, angles, hooks |
| Writer | `AGENT-02-WRITER.md` | Draft generation |
| Style Enforcer | `AGENT-03-STYLE-ENFORCER.md` | Tone/voice matching |
| Engagement Optimizer | `AGENT-04-ENGAGEMENT-OPTIMIZER.md` | Platform engagement |
| Critic | `AGENT-05-CRITIC.md` | Scoring & self-reflection |
| Visual Brief | `AGENT-06-VISUAL-BRIEF.md` | Visual asset directions |

## How It Works

1. Load `AGENTS.md` to get the agent registry
2. For each agent, load its individual file (`AGENT-NN-*.md`)
3. Extract YAML frontmatter as config dict
4. Use `system_prompt` field as the agent's system message
5. Override `defaults` with per-agent values

## Updating an Agent

Just edit the corresponding `AGENT-NN-*.md` file. The system loads it at runtime, so no Python code changes are required for prompt tuning.
