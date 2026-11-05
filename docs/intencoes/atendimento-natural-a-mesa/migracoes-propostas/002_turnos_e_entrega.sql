-- DRAFT DOCUMENTAL. Depende de 001. Não executar em produção.
BEGIN;
CREATE TABLE conversation_turns (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    conversation_id VARCHAR(36) NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 0),
    user_text TEXT NOT NULL,
    intent VARCHAR(80),
    context_summary TEXT,
    evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(24) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','processing','answered','cancelled','human','failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, conversation_id, revision),
    UNIQUE (tenant_id, conversation_id, id),
    FOREIGN KEY (tenant_id, conversation_id) REFERENCES conversations(tenant_id, id) ON DELETE CASCADE
);
-- Outbox pai continua com uma única resposta por revisão. Não remover uq_outbox_conversation_revision.
CREATE TABLE outbox_parts (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    conversation_id VARCHAR(36) NOT NULL,
    outbox_id VARCHAR(36) NOT NULL,
    part_index INTEGER NOT NULL CHECK (part_index >= 0),
    content TEXT NOT NULL,
    expected_revision INTEGER NOT NULL,
    expected_cancel_epoch INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(24) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','claimed','dispatching','accepted','delivered','read','cancelled','failed','unknown')),
    not_before TIMESTAMPTZ NOT NULL DEFAULT now(),
    lease_until TIMESTAMPTZ,
    claim_token VARCHAR(80),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    external_message_id VARCHAR(180),
    last_error_code VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, outbox_id, part_index),
    UNIQUE (tenant_id, conversation_id, id),
    FOREIGN KEY (tenant_id, conversation_id, outbox_id)
        REFERENCES outbox_messages(tenant_id, conversation_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_parts_due ON outbox_parts(status, not_before) WHERE status = 'pending';
CREATE INDEX ix_parts_conversation ON outbox_parts(tenant_id, conversation_id, outbox_id, part_index);
CREATE INDEX ix_parts_external ON outbox_parts(tenant_id, external_message_id);

CREATE TABLE conversation_events (
    id VARCHAR(36) PRIMARY KEY,
    tenant_id VARCHAR(36) NOT NULL,
    conversation_id VARCHAR(36) NOT NULL,
    event_key VARCHAR(160) NOT NULL,
    kind VARCHAR(60) NOT NULL,
    actor_kind VARCHAR(20) NOT NULL CHECK (actor_kind IN ('contact','operator','system','tool')),
    actor_id VARCHAR(80),
    -- Metadados minimizados: não guardar chave, URL temporária ou prompt completo.
    details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, conversation_id, event_key),
    FOREIGN KEY (tenant_id, conversation_id) REFERENCES conversations(tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX ix_events_timeline ON conversation_events(tenant_id, conversation_id, created_at);
COMMIT;
