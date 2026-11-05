-- Local SQLite staging only. Never run against application/production PostgreSQL.
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version VALUES(1);
CREATE TABLE IF NOT EXISTS sources(
 id INTEGER PRIMARY KEY, company TEXT NOT NULL, root TEXT NOT NULL, relative_path TEXT NOT NULL,
 sha256 TEXT NOT NULL, version TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL,
 error TEXT, UNIQUE(company,root,relative_path,sha256,version));
CREATE TABLE IF NOT EXISTS messages(
 id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES sources(id),
 ordinal INTEGER NOT NULL, date_raw TEXT, author TEXT, body TEXT NOT NULL,
 system INTEGER NOT NULL, UNIQUE(source_id,ordinal));
CREATE TABLE IF NOT EXISTS attachments(
 message_id INTEGER NOT NULL REFERENCES messages(id), source_id INTEGER REFERENCES sources(id),
 reference TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(message_id,reference));
CREATE TABLE IF NOT EXISTS transcriptions(
 id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES sources(id), recipe TEXT NOT NULL,
 status TEXT NOT NULL, error TEXT, duration REAL, elapsed REAL, language TEXT,
 UNIQUE(source_id,recipe));
CREATE TABLE IF NOT EXISTS segments(
 transcription_id INTEGER NOT NULL REFERENCES transcriptions(id), ordinal INTEGER NOT NULL,
 start REAL NOT NULL, end REAL NOT NULL, text TEXT NOT NULL, avg_logprob REAL,
 no_speech_prob REAL, PRIMARY KEY(transcription_id,ordinal));
CREATE TABLE IF NOT EXISTS proposals(
 id INTEGER PRIMARY KEY, company TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('fact','example')),
 text TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending_review', reviewer TEXT,
 reviewed_at TEXT, valid_until TEXT, redaction_version TEXT NOT NULL, UNIQUE(company,kind,text));
CREATE TABLE IF NOT EXISTS proposal_messages(
 proposal_id INTEGER NOT NULL REFERENCES proposals(id), message_id INTEGER NOT NULL REFERENCES messages(id),
 PRIMARY KEY(proposal_id,message_id));
