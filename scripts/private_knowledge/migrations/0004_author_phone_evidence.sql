CREATE TABLE IF NOT EXISTS author_phone_evidence (
    id INTEGER PRIMARY KEY,
    company TEXT NOT NULL,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    author_id INTEGER REFERENCES conversation_authors(id) ON DELETE SET NULL,
    message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    phone_e164 TEXT NOT NULL,
    evidence_type TEXT NOT NULL CHECK(evidence_type IN ('author_label','message_body')),
    status TEXT NOT NULL CHECK(status IN ('confirmed','pending_review','rejected')),
    UNIQUE(source_id, author_id, message_id, phone_e164, evidence_type)
);
CREATE INDEX IF NOT EXISTS ix_author_phone_evidence_company_phone
    ON author_phone_evidence(company, phone_e164);
