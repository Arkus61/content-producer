-- Memory Graph Schema for Content Producer v2
-- Requires: PostgreSQL 14+ with pgvector extension

CREATE EXTENSION IF NOT EXISTS vector;

-- ── Nodes: facts, topics, hooks, metrics, etc. ──

CREATE TABLE IF NOT EXISTS memory_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expert_id TEXT NOT NULL,
    agent_id TEXT NOT NULL DEFAULT 'memory',
    node_type TEXT NOT NULL,
    label TEXT NOT NULL,
    embedding VECTOR(1536),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_confirmed_at TIMESTAMPTZ DEFAULT now(),
    evidence_count INT DEFAULT 1,
    confidence FLOAT DEFAULT 0.5,
    is_archived BOOLEAN DEFAULT false,
    archived_at TIMESTAMPTZ
);

-- ── Edges: relationships between nodes ──

CREATE TABLE IF NOT EXISTS memory_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expert_id TEXT NOT NULL,
    from_node_id UUID REFERENCES memory_nodes(id) ON DELETE CASCADE,
    to_node_id UUID REFERENCES memory_nodes(id) ON DELETE CASCADE,
    relation TEXT NOT NULL,
    weight FLOAT DEFAULT 0.5,
    evidence_count INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_confirmed_at TIMESTAMPTZ DEFAULT now(),
    is_tombstone BOOLEAN DEFAULT false,
    tombstoned_at TIMESTAMPTZ
);

-- ── Pipeline runs: full trace of each generation ──

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expert_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'telegram',
    content_type TEXT NOT NULL DEFAULT 'post',
    final_score FLOAT,
    iterations INT DEFAULT 1,
    tokens_prompt INT DEFAULT 0,
    tokens_completion INT DEFAULT 0,
    latency_ms FLOAT DEFAULT 0.0,
    trace JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ── Spans: per-agent call tracing ──

CREATE TABLE IF NOT EXISTS agent_spans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    trace_id TEXT,
    span_id TEXT,
    parent_span_id TEXT,
    from_agent TEXT NOT NULL,
    to_agent TEXT,
    task_type TEXT NOT NULL,
    status TEXT DEFAULT 'started',
    skills_used JSONB DEFAULT '[]'::jsonb,
    tokens_prompt INT DEFAULT 0,
    tokens_completion INT DEFAULT 0,
    latency_ms FLOAT DEFAULT 0.0,
    error TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ
);

-- ── Indexes ──

CREATE INDEX IF NOT EXISTS idx_memory_nodes_expert ON memory_nodes(expert_id);
CREATE INDEX IF NOT EXISTS idx_memory_nodes_type ON memory_nodes(expert_id, node_type);
CREATE INDEX IF NOT EXISTS idx_memory_edges_expert ON memory_edges(expert_id);
CREATE INDEX IF NOT EXISTS idx_memory_edges_tombstone ON memory_edges(expert_id, is_tombstone);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_expert ON pipeline_runs(expert_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_score ON pipeline_runs(expert_id, final_score DESC);
CREATE INDEX IF NOT EXISTS idx_agent_spans_run ON agent_spans(run_id);
