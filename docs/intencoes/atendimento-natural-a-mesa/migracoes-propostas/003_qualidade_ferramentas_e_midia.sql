-- DRAFT DOCUMENTAL. Depende de 001 e 002. Sem backfill/ativação automática.
BEGIN;
CREATE TABLE conversation_quality_cases (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    conversation_id VARCHAR(36) NOT NULL,
    turn_id VARCHAR(36),
    reason VARCHAR(100) NOT NULL,
    feedback TEXT,
    proposed_resolution TEXT,
    status VARCHAR(24) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','reviewed','approved','rejected','archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    FOREIGN KEY (tenant_id, conversation_id) REFERENCES conversations(tenant_id, id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, conversation_id, turn_id) REFERENCES conversation_turns(tenant_id, conversation_id, id)
);
CREATE INDEX ix_quality_queue ON conversation_quality_cases(tenant_id, status, created_at);

CREATE TABLE tenant_tool_configs (
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    tool_key VARCHAR(100) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT false,
    effect VARCHAR(16) NOT NULL CHECK (effect IN ('read','write')),
    requires_approval BOOLEAN NOT NULL DEFAULT true,
    -- Somente chaves de handlers registrados, não SQL/código/endpoints arbitrários.
    config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    credentials_encrypted TEXT,
    PRIMARY KEY (tenant_id, tool_key)
);
CREATE TABLE tool_executions (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    conversation_id VARCHAR(36) NOT NULL,
    turn_id VARCHAR(36) NOT NULL,
    tool_key VARCHAR(100) NOT NULL,
    idempotency_key VARCHAR(160) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','awaiting_approval','running','completed','rejected','failed','unknown')),
    args_redacted JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, idempotency_key),
    FOREIGN KEY (tenant_id, tool_key) REFERENCES tenant_tool_configs(tenant_id, tool_key),
    FOREIGN KEY (tenant_id, conversation_id, turn_id) REFERENCES conversation_turns(tenant_id, conversation_id, id) ON DELETE CASCADE
);

CREATE TABLE inbound_media_assets (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    conversation_id VARCHAR(36) NOT NULL,
    message_id VARCHAR(36) NOT NULL,
    mime_type VARCHAR(120),
    source_locator_encrypted TEXT,
    size_bytes BIGINT CHECK (size_bytes >= 0),
    status VARCHAR(24) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','processing','transcribed','failed','expired')),
    expires_at TIMESTAMPTZ NOT NULL,
    error_code VARCHAR(100),
    UNIQUE (tenant_id, message_id),
    FOREIGN KEY (tenant_id, conversation_id, message_id) REFERENCES messages(tenant_id, conversation_id, id) ON DELETE CASCADE
);
-- Transcrição em messages é conteúdo sensível: exige retenção também ali.
ALTER TABLE memory_items ADD COLUMN review_status VARCHAR(24) NOT NULL DEFAULT 'pending'
    CHECK (review_status IN ('pending','approved','rejected','expired'));
ALTER TABLE memory_items ADD COLUMN source_conversation_id VARCHAR(36);
ALTER TABLE memory_items ADD CONSTRAINT fk_memory_source_same_tenant
    FOREIGN KEY (tenant_id, source_conversation_id) REFERENCES conversations(tenant_id, id);
ALTER TABLE memory_items ADD COLUMN reviewed_at TIMESTAMPTZ;

CREATE TABLE contact_channel_permissions (
    tenant_id VARCHAR(36) NOT NULL,
    instance_id VARCHAR(36) NOT NULL,
    contact_key VARCHAR(180) NOT NULL,
    opted_out BOOLEAN NOT NULL DEFAULT false,
    permission_basis VARCHAR(100),
    evidence_reference VARCHAR(160),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, instance_id, contact_key),
    FOREIGN KEY (tenant_id, instance_id) REFERENCES zapi_instances(tenant_id, id) ON DELETE CASCADE
);
-- Preferências de fallback de provedor, sem expor segredos no JSON de política.
CREATE TABLE tenant_provider_fallbacks (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    priority INTEGER NOT NULL CHECK (priority > 0),
    provider VARCHAR(40) NOT NULL,
    base_url VARCHAR(500) NOT NULL,
    model VARCHAR(160) NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (tenant_id, priority)
);
COMMIT;
