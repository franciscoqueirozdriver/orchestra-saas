"""Shared isolated-PostgreSQL fixtures; the test modules keep their own skip guard."""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

URL = os.environ.get('TEST_DATABASE_URL', '')
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def engine():
    if not URL:
        pytest.skip('requires explicitly isolated PostgreSQL')
    parsed = make_url(URL)
    assert parsed.database == 'orchestra_consolidation_test'
    assert parsed.host in {'127.0.0.1', 'orchestra-consolidation-test-db-20261105', 'orchestra-natural-test-db-20261105'}
    engine = create_engine(URL, pool_size=12, max_overflow=8)
    with engine.begin() as c:
        c.execute(text('DROP SCHEMA public CASCADE'))
        c.execute(text('CREATE SCHEMA public'))
        c.execute(text('CREATE EXTENSION vector'))
    env = dict(os.environ, DATABASE_URL=URL, PYTHONPATH=str(ROOT / 'backend'))
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT / 'backend', env=env, check=True, capture_output=True)
    yield engine
    engine.dispose()


@pytest.fixture
def runtime(engine, monkeypatch):
    from app import database, locks, tasks, outbox, scheduler
    from app.models import Base, Tenant, Agent, Conversation, LLMConfig, ZapiInstance
    from app.security import encrypt_secret, hash_callback_secret
    # This fixture is scoped to the named disposable database above.
    with engine.begin() as c:
        c.execute(text('TRUNCATE ' + ','.join('"'+t.name+'"' for t in Base.metadata.sorted_tables) + ' CASCADE'))
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(database, 'engine', engine)
    monkeypatch.setattr(locks, 'engine', engine)
    monkeypatch.setattr(tasks, 'SessionLocal', factory)
    monkeypatch.setattr(outbox, 'SessionLocal', factory)
    monkeypatch.setattr(tasks.settings, 'outbound_enabled', True)
    monkeypatch.setattr(tasks.settings, 'message_group_window_seconds', 0)
    monkeypatch.setattr(tasks, '_schedule_reply', lambda *args: None)
    monkeypatch.setattr(tasks.dispatch_outbox, 'delay', lambda *a: None)
    monkeypatch.setattr(tasks.process_webhook_event, 'delay', lambda *a: None)
    def deny(*args, **kwargs):
        raise AssertionError('Unexpected external request in isolated tests')
    monkeypatch.setattr('app.zapi_client.ZapiClient._request', deny)
    monkeypatch.setattr('app.llm_client.httpx.post', deny)
    monkeypatch.setattr('app.embedding_client.httpx.post', deny)
    with factory() as db:
        db.add_all([Tenant(id='tenant-a', name='Synthetic A', slug='synthetic-a'), Tenant(id='tenant-b', name='Synthetic B', slug='synthetic-b')]);db.flush()
        db.add_all([Agent(id='agent-a', tenant_id='tenant-a', name='Synthetic agent', enabled=True, auto_reply_enabled=True), Agent(id='agent-b', tenant_id='tenant-b', name='Other agent')]);db.flush()
        db.add(LLMConfig(id='model-a', tenant_id='tenant-a', name='Synthetic', provider='openai-compatible', base_url='https://provider.invalid/v1', model='synthetic', embedding_model='synthetic', api_key_encrypted=encrypt_secret('test-only-model-key'), is_default=True));db.flush()
        db.add(ZapiInstance(id='instance-a', tenant_id='tenant-a', agent_id='agent-a', label='Synthetic', instance_id='external-a', token_encrypted=encrypt_secret('test-only-zapi-token'), callback_token_hash=hash_callback_secret('test-only-callback-secret'), sending_enabled=True, status='connected'))
        db.flush()
        db.add(Conversation(id='conversation-a', tenant_id='tenant-a', instance_id='instance-a', contact_key='synthetic-contact', status='open', revision=1, last_incoming_at=datetime.now(timezone.utc)-timedelta(minutes=1)))
        db.commit()
    return SimpleNamespace(db=factory, tasks=tasks, outbox=outbox, engine=engine, admin=SimpleNamespace(role='tenant_admin'))
