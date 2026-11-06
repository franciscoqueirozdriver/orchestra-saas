import io
import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (Agent, Conversation, ConversationContactAlias,
                        HistoricalImportBatch, LLMConfig, Message, Tenant,
                        User, ZapiInstance)
from app import history_import


def test_history_import_is_visible_idempotent_and_tenant_scoped(tmp_path, monkeypatch):
    engine=create_engine(f"sqlite:///{tmp_path/'history-test.sqlite'}")
    tables=[Tenant.__table__,User.__table__,LLMConfig.__table__,Agent.__table__,
            ZapiInstance.__table__,Conversation.__table__,HistoricalImportBatch.__table__,
            ConversationContactAlias.__table__,Message.__table__]
    Base.metadata.create_all(engine,tables=tables)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    monkeypatch.setattr(history_import,'SessionLocal',factory)
    tenant='tenant-test';instance='instance-test'
    with factory.begin() as db:
        db.add(Tenant(id=tenant,name='Synthetic',slug='synthetic'))
        db.add(ZapiInstance(id=instance,tenant_id=tenant,label='Synthetic',instance_id='synthetic-external',
            token_encrypted='test',callback_token_hash='test-hash',status='not_checked'))
    rows=[
        {'tenant_id':tenant,'instance_id':instance,'source_sha256':'a'*64,'source_version':'test-v1',
         'source_timezone':'America/Sao_Paulo','contact_key':'5511912345678','contact_name':'Contato sintético',
         'ordinal':0,'original_timestamp_text':'01/11/2026 10:00','created_at':'2026-11-01T13:00:00+00:00',
         'direction':'incoming','author_kind':'user','author_name':'Cliente fictício','kind':'text',
         'content':'mensagem sintética','status':'historical'},
        {'tenant_id':tenant,'instance_id':instance,'source_sha256':'a'*64,'source_version':'test-v1',
         'source_timezone':'America/Sao_Paulo','contact_key':'5511912345678','contact_name':'Contato sintético',
         'ordinal':1,'original_timestamp_text':'01/11/2026 10:01','created_at':'2026-11-01T13:01:00+00:00',
         'direction':'outgoing','author_kind':'operator','author_name':'Atendente fictício','kind':'text',
         'content':'resposta sintética','status':'historical'},
    ]
    package=''.join(json.dumps(row)+'\n' for row in rows)
    dry=history_import.import_history(io.StringIO(package),tenant,instance)
    assert dry['applied'] is False and dry['new_conversations']==1
    done=history_import.import_history(io.StringIO(package),tenant,instance,apply=True)
    assert done['imported_messages']==2
    repeated=history_import.import_history(io.StringIO(package),tenant,instance,apply=True)
    assert repeated['sources_to_import']==0 and repeated['imported_messages']==0
    with factory() as db:
        conversation=db.scalar(select(Conversation).where(Conversation.tenant_id==tenant))
        messages=db.scalars(select(Message).where(Message.conversation_id==conversation.id).order_by(Message.history_source_ordinal)).all()
        assert conversation.history_only is True and conversation.consent_status=='unknown'
        assert [(m.author_name,m.author_kind,m.direction,m.status) for m in messages]==[
            ('Cliente fictício','user','incoming','historical'),
            ('Atendente fictício','operator','outgoing','historical')]
        assert db.query(HistoricalImportBatch).count()==1
        assert db.query(ConversationContactAlias).count()==1
        assert conversation.last_incoming_at.replace(tzinfo=timezone.utc)==datetime(2026,11,1,13,0,tzinfo=timezone.utc)
    engine.dispose()


def test_history_import_rejects_other_tenant_and_duplicate_ordinals():
    record={'tenant_id':'tenant-a','instance_id':'instance-a','source_sha256':'b'*64,
            'source_version':'test-v1','source_timezone':'UTC','contact_key':'history:test',
            'contact_name':'','ordinal':0,'original_timestamp_text':'','created_at':'2026-01-01T00:00:00+00:00',
            'direction':'historical','author_kind':'system','author_name':'Sistema','kind':'system',
            'content':'sintético','status':'historical'}
    with __import__('pytest').raises(ValueError,match='tenant/instância'):
        history_import.read_records(io.StringIO(json.dumps(record)+'\n'),'tenant-b','instance-a')
    duplicate=dict(record)
    with __import__('pytest').raises(ValueError,match='ordinais duplicados'):
        history_import.read_records(io.StringIO(json.dumps(record)+'\n'+json.dumps(duplicate)+'\n'),'tenant-a','instance-a')
