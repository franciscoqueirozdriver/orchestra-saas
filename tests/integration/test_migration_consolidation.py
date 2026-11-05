"""Opt-in tests: only the explicitly named disposable database is allowed.

Never use a production DSN. Run with tests/run-isolated.sh as documented.
"""
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, text
import pgvector.sqlalchemy  # Registers vector reflection for schema equivalence.
from sqlalchemy.engine import make_url

URL = os.environ.get('TEST_DATABASE_URL', '')
BASELINE = os.environ.get('ORCHESTRA_BASELINE_ROOT', '')
pytestmark = pytest.mark.skipif(not URL or not BASELINE, reason='requires isolated PostgreSQL and original source baseline')
ROOT = Path(__file__).resolve().parents[2]


def alembic(root, *args, success=True):
    env = dict(os.environ, DATABASE_URL=URL, PYTHONPATH=str(root / 'backend'), ENVIRONMENT='test')
    result = subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=root / 'backend', env=env, capture_output=True, text=True)
    if success:
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0
    return result


def shape(engine):
    view = inspect(engine)
    result = {}
    for table in sorted(view.get_table_names()):
        if table == 'alembic_version':
            continue
        result[table] = {
            'columns': [(c['name'], str(c['type']), c['nullable'], c['default']) for c in view.get_columns(table)],
            'pk': view.get_pk_constraint(table)['constrained_columns'],
            'indexes': sorted((i['name'], tuple(i['column_names']), bool(i['unique']), str(i.get('dialect_options', {}))) for i in view.get_indexes(table)),
            'unique': sorted((u['name'], tuple(u['column_names'])) for u in view.get_unique_constraints(table)),
            'fks': sorted((tuple(f['constrained_columns']), f['referred_table'], tuple(f['referred_columns']), str(f['options'])) for f in view.get_foreign_keys(table)),
        }
    return result


def reset(engine):
    with engine.begin() as c:
        c.execute(text('DROP SCHEMA public CASCADE'))
        c.execute(text('CREATE SCHEMA public'))
        c.execute(text('CREATE EXTENSION vector'))


def seed(engine):
    with engine.begin() as c:
        c.execute(text("INSERT INTO tenants(id,name,slug,is_active) VALUES ('tenant-a','Synthetic A','synthetic-a',true)"))
        c.execute(text("INSERT INTO agents(id,tenant_id,name,description,system_prompt,enabled,auto_reply_enabled) VALUES ('agent-a','tenant-a','Synthetic agent','','',true,false)"))
        c.execute(text("INSERT INTO llm_configs(id,tenant_id,provider,base_url,model,embedding_model,api_key_encrypted) VALUES ('llm-a','tenant-a','openai-compatible','https://provider.invalid/v1','synthetic','synthetic','synthetic-ciphertext')"))
        c.execute(text("INSERT INTO zapi_instances(id,tenant_id,label,instance_id,token_encrypted,callback_token_hash,status,webhook_configured,is_active) VALUES ('instance-a','tenant-a','Synthetic','external-synthetic','synthetic-ciphertext','synthetic-hash','not_checked',false,true)"))
        c.execute(text("INSERT INTO conversations(id,tenant_id,instance_id,contact_key,contact_name,status,revision) VALUES ('conversation-a','tenant-a','instance-a','synthetic-contact','','open',1)"))
        c.execute(text("INSERT INTO messages(id,tenant_id,conversation_id,direction,kind,content,status) VALUES ('message-a','tenant-a','conversation-a','incoming','text','synthetic only','received')"))


def test_frozen_initial_and_legacy_upgrade_preserve_schema_and_synthetic_data():
    parsed = make_url(URL)
    assert parsed.database == 'orchestra_consolidation_test'
    assert parsed.host in {'orchestra-consolidation-test-db-20261105', 'orchestra-natural-test-db-20261105', '127.0.0.1'}
    engine = create_engine(URL)
    baseline = Path(BASELINE)
    try:
        reset(engine)
        alembic(baseline, 'upgrade', 'head')
        legacy = shape(engine)
        seed(engine)
        # This is the actual production route: existing 0001 -> new 0002 -> 0003.
        alembic(ROOT, 'upgrade', 'head')
        upgraded = shape(engine)
        with engine.connect() as c:
            assert c.scalar(text('SELECT version_num FROM alembic_version')) == '0005_conversation_core'
            assert c.scalar(text("SELECT count(*) FROM messages WHERE content='synthetic only'")) == 1
            assert c.scalar(text("SELECT last_incoming_at IS NOT NULL FROM conversations WHERE id='conversation-a'"))
            assert c.scalar(text("SELECT is_default FROM llm_configs WHERE id='llm-a'"))
            assert c.scalar(text("SELECT agent_id IS NULL FROM zapi_instances WHERE id='instance-a'"))
        alembic(ROOT, 'check')
        # More than one provider must refuse downgrade without losing connections.
        with engine.begin() as c:
            c.execute(text("INSERT INTO llm_configs(id,tenant_id,provider,base_url,model,embedding_model,api_key_encrypted) VALUES ('llm-b','tenant-a','openai-compatible','https://provider.invalid/v1','synthetic','synthetic','synthetic-ciphertext')"))
        failed = alembic(ROOT, 'downgrade', '0002_delivery_controls', success=False)
        assert 'Downgrade recusado' in failed.stderr
        with engine.begin() as c:
            assert c.scalar(text('SELECT version_num FROM alembic_version')) == '0005_conversation_core'
            assert c.scalar(text('SELECT count(*) FROM llm_configs')) == 2
            c.execute(text("DELETE FROM llm_configs WHERE id='llm-b'"))
        alembic(ROOT, 'downgrade', '0001_initial')
        assert shape(engine) == legacy
        alembic(ROOT, 'upgrade', 'head')
        assert shape(engine) == upgraded
        # Fresh frozen initial must match the original code, not current metadata.
        reset(engine)
        alembic(ROOT, 'upgrade', '0001_initial')
        assert shape(engine) == legacy
        alembic(ROOT, 'upgrade', 'head')
        assert shape(engine) == upgraded
        alembic(ROOT, 'check')
    finally:
        engine.dispose()
