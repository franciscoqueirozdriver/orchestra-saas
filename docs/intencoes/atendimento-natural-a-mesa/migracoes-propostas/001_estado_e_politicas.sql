-- DRAFT DOCUMENTAL. Não aplicar: converter para Alembic e models após revisão.
-- Schema base: Orquestra f6d0e2a. UUIDs da aplicação são VARCHAR(36).
BEGIN;
ALTER TABLE conversations ADD CONSTRAINT uq_conversation_tenant_id UNIQUE (tenant_id, id);
ALTER TABLE agents ADD CONSTRAINT uq_agent_tenant_id UNIQUE (tenant_id, id);
ALTER TABLE zapi_instances ADD CONSTRAINT uq_instance_tenant_id UNIQUE (tenant_id, id);
ALTER TABLE messages ADD CONSTRAINT uq_message_tenant_conversation_id UNIQUE (tenant_id, conversation_id, id);
ALTER TABLE outbox_messages ADD CONSTRAINT uq_outbox_tenant_conversation_id UNIQUE (tenant_id, conversation_id, id);

CREATE TABLE tenant_conversation_policies (
    tenant_id VARCHAR(36) PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    features JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(features) = 'object'),
    -- Ausência de flag significa desabilitado. Default de debounce preserva 3s.
    debounce_ms INTEGER NOT NULL DEFAULT 3000 CHECK (debounce_ms BETWEEN 0 AND 15000),
    max_debounce_ms INTEGER NOT NULL DEFAULT 30000 CHECK (max_debounce_ms BETWEEN 1000 AND 60000),
    idle_minutes INTEGER NOT NULL DEFAULT 30 CHECK (idle_minutes BETWEEN 1 AND 1440),
    max_clarifications INTEGER NOT NULL DEFAULT 1 CHECK (max_clarifications BETWEEN 0 AND 3),
    chunk_chars INTEGER NOT NULL DEFAULT 900 CHECK (chunk_chars BETWEEN 200 AND 3500),
    timezone VARCHAR(80) NOT NULL DEFAULT 'America/Sao_Paulo',
    operation_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (max_debounce_ms >= debounce_ms)
);
ALTER TABLE agents ADD COLUMN persona_config JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE zapi_instances ADD COLUMN default_agent_id VARCHAR(36);
ALTER TABLE zapi_instances ADD CONSTRAINT fk_instance_agent_same_tenant
    FOREIGN KEY (tenant_id, default_agent_id) REFERENCES agents(tenant_id, id);
-- Agente referenciado não pode ser excluído sem desvincular atribuições.

CREATE TABLE conversation_runtime_states (
    tenant_id VARCHAR(36) NOT NULL,
    conversation_id VARCHAR(36) NOT NULL,
    assigned_agent_id VARCHAR(36),
    mode VARCHAR(16) NOT NULL DEFAULT 'ai' CHECK (mode IN ('ai','human','paused')),
    flow_key VARCHAR(80),
    step_key VARCHAR(80),
    context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    version INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
    cancel_epoch INTEGER NOT NULL DEFAULT 0 CHECK (cancel_epoch >= 0),
    clarification_count INTEGER NOT NULL DEFAULT 0 CHECK (clarification_count >= 0),
    last_inbound_at TIMESTAMPTZ,
    turn_started_at TIMESTAMPTZ,
    resume_after TIMESTAMPTZ,
    -- User id em ator de auditoria é validado pelo serviço e registrado em eventos.
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, conversation_id),
    FOREIGN KEY (tenant_id, conversation_id) REFERENCES conversations(tenant_id, id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, assigned_agent_id) REFERENCES agents(tenant_id, id)
);
CREATE INDEX ix_runtime_mode_updated ON conversation_runtime_states(tenant_id, mode, updated_at);
COMMIT;
