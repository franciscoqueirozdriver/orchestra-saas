-- Private staging only. A display name is scoped to one exported conversation.
CREATE TABLE IF NOT EXISTS conversation_authors (
    id INTEGER PRIMARY KEY,
    company TEXT NOT NULL,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    link_status TEXT NOT NULL DEFAULT 'unresolved'
        CHECK (link_status IN ('unresolved','phone_identified','linked','rejected')),
    phone_e164 TEXT,
    whatsapp_contact_key TEXT,
    UNIQUE(source_id, display_name),
    CHECK ((link_status = 'phone_identified' AND phone_e164 IS NOT NULL AND whatsapp_contact_key IS NULL)
        OR (link_status = 'linked' AND whatsapp_contact_key IS NOT NULL)
        OR (link_status IN ('unresolved','rejected') AND whatsapp_contact_key IS NULL))
);
CREATE INDEX IF NOT EXISTS ix_conversation_authors_company_contact
    ON conversation_authors(company, whatsapp_contact_key);

ALTER TABLE messages ADD COLUMN author_id INTEGER
    REFERENCES conversation_authors(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_messages_author_id ON messages(author_id);

CREATE TABLE IF NOT EXISTS contact_cards (
    id INTEGER PRIMARY KEY,
    company TEXT NOT NULL,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    card_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    phone_e164 TEXT,
    UNIQUE(source_id, card_key)
);
CREATE INDEX IF NOT EXISTS ix_contact_cards_company_phone
    ON contact_cards(company, phone_e164);

CREATE TABLE IF NOT EXISTS author_contact_candidates (
    author_id INTEGER NOT NULL REFERENCES conversation_authors(id) ON DELETE CASCADE,
    contact_card_id INTEGER NOT NULL REFERENCES contact_cards(id) ON DELETE CASCADE,
    match_method TEXT NOT NULL CHECK(match_method IN ('exact_name','exact_phone')),
    status TEXT NOT NULL DEFAULT 'pending_review'
        CHECK(status IN ('pending_review','confirmed','rejected')),
    PRIMARY KEY(author_id, contact_card_id, match_method)
);
