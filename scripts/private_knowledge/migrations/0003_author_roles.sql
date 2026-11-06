ALTER TABLE conversation_authors ADD COLUMN speaker_role TEXT NOT NULL DEFAULT 'unresolved'
    CHECK (speaker_role IN ('unresolved','staff','customer'));
CREATE INDEX IF NOT EXISTS ix_conversation_authors_company_role
    ON conversation_authors(company, speaker_role);
