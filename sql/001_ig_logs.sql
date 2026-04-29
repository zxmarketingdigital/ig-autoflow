-- Tabela de logs de operacao do auto-responder Instagram
-- Executar via Supabase ou SQLite local

CREATE TABLE IF NOT EXISTS ig_comment_log (
    id          SERIAL PRIMARY KEY,
    comment_id  TEXT NOT NULL UNIQUE,
    media_id    TEXT NOT NULL,
    username    TEXT,
    keyword     TEXT,
    reply_sent  BOOLEAN DEFAULT FALSE,
    dm_sent     BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ DEFAULT NOW(),
    error       TEXT
);

CREATE TABLE IF NOT EXISTS ig_dm_log (
    id              SERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    sender_id       TEXT NOT NULL,
    message_preview TEXT,
    response_sent   BOOLEAN DEFAULT FALSE,
    escalated       BOOLEAN DEFAULT FALSE,
    processed_at    TIMESTAMPTZ DEFAULT NOW(),
    error           TEXT
);

CREATE INDEX IF NOT EXISTS idx_ig_comment_log_comment_id ON ig_comment_log(comment_id);
CREATE INDEX IF NOT EXISTS idx_ig_dm_log_conversation_id ON ig_dm_log(conversation_id);
