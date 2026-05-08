-- ─────────────────────────────────────────────────────────────────────────────
-- AEGIS Database Schema v1.0
-- ─────────────────────────────────────────────────────────────────────────────

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ─── Users ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email       VARCHAR(255) UNIQUE NOT NULL,
  name        VARCHAR(255),
  clerk_id    VARCHAR(255) UNIQUE,
  tier        VARCHAR(50) DEFAULT 'starter' CHECK (tier IN ('starter', 'professional', 'enterprise')),
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Investigations ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investigations (
  id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id              UUID REFERENCES users(id) ON DELETE CASCADE,
  target_url           TEXT NOT NULL,
  company_name         VARCHAR(500),
  investigation_type   VARCHAR(50) NOT NULL DEFAULT 'competitive'
                         CHECK (investigation_type IN ('competitive', 'due_diligence', 'ipo_readiness', 'market_analysis')),
  strategy_config      JSONB DEFAULT '{}',
  status               VARCHAR(50) DEFAULT 'queued'
                         CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
  confidence_score     DECIMAL(3,2) CHECK (confidence_score BETWEEN 0 AND 1),
  vitality_score       INTEGER CHECK (vitality_score BETWEEN 0 AND 100),
  moat_score           INTEGER CHECK (moat_score BETWEEN 0 AND 100),
  risk_score           INTEGER CHECK (risk_score BETWEEN 0 AND 100),
  red_flags            JSONB DEFAULT '[]',
  metadata             JSONB DEFAULT '{}',
  created_at           TIMESTAMPTZ DEFAULT NOW(),
  started_at           TIMESTAMPTZ,
  completed_at         TIMESTAMPTZ,
  total_cost_usd       DECIMAL(10,4),
  total_tokens         INTEGER,
  duration_ms          INTEGER
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_investigations_user    ON investigations(user_id);
CREATE INDEX IF NOT EXISTS idx_investigations_status  ON investigations(status);
CREATE INDEX IF NOT EXISTS idx_investigations_url     ON investigations(target_url);
CREATE INDEX IF NOT EXISTS idx_investigations_created ON investigations(created_at DESC);

-- ─── Reports ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reports (
  id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  investigation_id  UUID REFERENCES investigations(id) ON DELETE CASCADE,
  executive_summary TEXT,
  bull_thesis       TEXT,
  bear_thesis       TEXT,
  skeptic_analysis  TEXT,
  final_verdict     TEXT,
  red_flag_matrix   JSONB DEFAULT '[]',
  moat_analysis     JSONB DEFAULT '{}',
  scenarios         JSONB DEFAULT '{}',
  comparable_cos    JSONB DEFAULT '[]',
  recommendations   JSONB DEFAULT '[]',
  raw_markdown      TEXT,
  pdf_url           TEXT,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_reports_investigation ON reports(investigation_id);

-- ─── Agent Logs ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_logs (
  id               BIGSERIAL PRIMARY KEY,
  investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
  agent_type       VARCHAR(100) NOT NULL,
  event_type       VARCHAR(100) NOT NULL
                     CHECK (event_type IN ('started', 'in_progress', 'completed', 'failed', 'timeout')),
  current_action   TEXT,
  confidence       DECIMAL(3,2),
  evidence_count   INTEGER DEFAULT 0,
  tokens_used      INTEGER,
  latency_ms       INTEGER,
  metadata         JSONB DEFAULT '{}',
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_logs_investigation ON agent_logs(investigation_id);
CREATE INDEX IF NOT EXISTS idx_agent_logs_type          ON agent_logs(agent_type);
CREATE INDEX IF NOT EXISTS idx_agent_logs_created       ON agent_logs(created_at DESC);

-- ─── Experiences (Few-Shot Bank) ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS experiences (
  id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  investigation_id UUID REFERENCES investigations(id) ON DELETE SET NULL,
  task_type        VARCHAR(100) NOT NULL,
  input_embedding  vector(1536),  -- OpenAI text-embedding-3-small dimension
  input_text       TEXT,
  reasoning        TEXT,
  output           JSONB,
  outcome          VARCHAR(50) CHECK (outcome IN ('success', 'failure', 'partial')),
  user_feedback    INTEGER CHECK (user_feedback BETWEEN 1 AND 5),
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_experiences_task      ON experiences(task_type);
CREATE INDEX IF NOT EXISTS idx_experiences_outcome   ON experiences(outcome);
CREATE INDEX IF NOT EXISTS idx_experiences_embedding ON experiences
  USING ivfflat (input_embedding vector_cosine_ops) WITH (lists = 100);

-- ─── Prompt Versions (Genetic Algorithm) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS prompt_versions (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  agent_type  VARCHAR(100) NOT NULL,
  task_type   VARCHAR(100) NOT NULL,
  content     TEXT NOT NULL,
  generation  INTEGER DEFAULT 0,
  fitness     DECIMAL(5,4),
  is_active   BOOLEAN DEFAULT false,
  parent_ids  UUID[],
  metadata    JSONB DEFAULT '{}',
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prompts_agent    ON prompt_versions(agent_type, is_active);
CREATE INDEX IF NOT EXISTS idx_prompts_fitness  ON prompt_versions(fitness DESC);

-- ─── Triggers ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trigger_configs (
  id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
  user_id          UUID REFERENCES users(id) ON DELETE CASCADE,
  conditions       JSONB NOT NULL DEFAULT '[]',
  webhook_url      TEXT,
  frequency        VARCHAR(50) DEFAULT 'daily' CHECK (frequency IN ('realtime', 'hourly', 'daily')),
  is_active        BOOLEAN DEFAULT true,
  last_triggered   TIMESTAMPTZ,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Webhook Events ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS webhook_events (
  id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  trigger_id       UUID REFERENCES trigger_configs(id) ON DELETE SET NULL,
  investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
  trigger_type     VARCHAR(100),
  payload          JSONB,
  delivered        BOOLEAN DEFAULT false,
  delivered_at     TIMESTAMPTZ,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Knowledge Snapshots ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_snapshots (
  id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
  snapshot_type    VARCHAR(100),
  data             JSONB,
  captured_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Update Trigger ───────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
- -    % % %  D e f a u l t   D a t a    % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 
 I N S E R T   I N T O   u s e r s   ( i d ,   e m a i l ,   n a m e ,   t i e r )   V A L U E S   ( ' 0 0 0 0 0 0 0 0 - 0 0 0 0 - 0 0 0 0 - 0 0 0 0 - 0 0 0 0 0 0 0 0 0 0 0 0 ' ,   ' d e m o @ a e g i s . a i ' ,   ' D e m o   U s e r ' ,   ' s t a r t e r ' )   O N   C O N F L I C T   ( i d )   D O   N O T H I N G ;  
 