"""One-time, idempotent importer for a private WhatsApp history JSONL stream."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import re
import sys
import uuid

from app.database import SessionLocal
from app.models import (Conversation, ConversationContactAlias, HistoricalImportBatch,
                        Message, Tenant, ZapiInstance)

VALID_DIRECTIONS = {'incoming', 'outgoing', 'historical'}
VALID_AUTHORS = {'user', 'operator', 'system', 'legacy'}
MAX_RECORD_BYTES = 2_000_000


def read_records(stream, tenant_id, instance_id):
    batches = defaultdict(list)
    expected = {'tenant_id': tenant_id, 'instance_id': instance_id}
    for line_number, line in enumerate(stream, 1):
        if len(line.encode('utf-8')) > MAX_RECORD_BYTES:
            raise ValueError(f'Linha {line_number} excede o limite de importação')
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, UnicodeError):
            raise ValueError(f'Linha {line_number} inválida') from None
        if not isinstance(row, dict) or any(row.get(k) != v for k, v in expected.items()):
            raise ValueError(f'Linha {line_number} não pertence ao tenant/instância de destino')
        source_hash = row.get('source_sha256')
        if not isinstance(source_hash, str) or not re.fullmatch(r'[a-f0-9]{64}', source_hash):
            raise ValueError(f'Linha {line_number} sem hash de origem válido')
        if row.get('direction') not in VALID_DIRECTIONS or row.get('author_kind') not in VALID_AUTHORS:
            raise ValueError(f'Linha {line_number} com papel/direção inválidos')
        if not isinstance(row.get('ordinal'), int) or row['ordinal'] < 0:
            raise ValueError(f'Linha {line_number} com ordem inválida')
        if not isinstance(row.get('content'), str) or not isinstance(row.get('original_timestamp_text'), str):
            raise ValueError(f'Linha {line_number} sem conteúdo/data válidos')
        contact_key = row.get('contact_key')
        if not isinstance(contact_key, str) or not contact_key or len(contact_key) > 180:
            raise ValueError(f'Linha {line_number} com identificador de contato inválido')
        try:
            stamp = datetime.fromisoformat(row['created_at'])
        except (TypeError, ValueError):
            raise ValueError(f'Linha {line_number} com data normalizada inválida') from None
        if stamp.tzinfo is None:
            raise ValueError(f'Linha {line_number} sem fuso horário')
        row['created_at_dt'] = stamp.astimezone(timezone.utc)
        batches[source_hash].append(row)
    if not batches:
        raise ValueError('Pacote de histórico vazio')
    for source_hash, rows in batches.items():
        rows.sort(key=lambda x: x['ordinal'])
        first = rows[0]
        ordinals = [x['ordinal'] for x in rows]
        if len(set(ordinals)) != len(ordinals):
            raise ValueError('Origem contém ordinais duplicados')
        for row in rows:
            if any(row.get(k) != first.get(k) for k in ('source_version','source_timezone','contact_key','contact_name')):
                raise ValueError('Metadados inconsistentes dentro da origem '+source_hash[:8])
    return batches


def _find_conversation(db, tenant_id, instance_id, contact_key):
    row = db.query(Conversation).filter_by(tenant_id=tenant_id, instance_id=instance_id,
                                           contact_key=contact_key).first()
    if row:
        return row
    alias = db.query(ConversationContactAlias).filter_by(tenant_id=tenant_id,
        instance_id=instance_id, contact_key=contact_key).first()
    if alias:
        return db.query(Conversation).filter_by(tenant_id=tenant_id,id=alias.conversation_id).first()
    return None


def _attach_alias(db, tenant_id, instance_id, conversation, contact_key):
    if not contact_key or contact_key.startswith('history:'):
        return False
    existing = db.query(ConversationContactAlias).filter_by(tenant_id=tenant_id,
        instance_id=instance_id, contact_key=contact_key).first()
    if existing:
        return existing.conversation_id == conversation.id
    db.add(ConversationContactAlias(id=str(uuid.uuid4()),tenant_id=tenant_id,
        instance_id=instance_id,conversation_id=conversation.id,contact_key=contact_key))
    return True


def import_history(stream, tenant_id, instance_id, apply=False):
    batches = read_records(stream, tenant_id, instance_id)
    db = SessionLocal()
    try:
        if not db.query(Tenant).filter_by(id=tenant_id).first():
            raise ValueError('Tenant de destino inexistente')
        if not db.query(ZapiInstance).filter_by(id=instance_id,tenant_id=tenant_id).first():
            raise ValueError('Instância não pertence ao tenant de destino')
        already = {r[0] for r in db.query(HistoricalImportBatch.source_sha256).filter(
            HistoricalImportBatch.tenant_id==tenant_id,
            HistoricalImportBatch.source_sha256.in_(list(batches))).all()}
        pending = {key: rows for key, rows in batches.items() if key not in already}
        conversations=set()
        for rows in pending.values():
            first=rows[0]
            if not _find_conversation(db,tenant_id,instance_id,first['contact_key']):
                conversations.add(first['contact_key'])
        report={'source_hashes':len(batches),'messages':sum(map(len,batches.values())),
            'already_imported_sources':len(already),'sources_to_import':len(pending),
            'new_conversations':len(conversations),'known_contact_keys':sum(
                not rows[0]['contact_key'].startswith('history:') for rows in pending.values())}
        if not apply:
            db.rollback()
            return {**report,'applied':False}

        db.commit()
        with db.begin():
            for source_hash, rows in pending.items():
                first=rows[0]
                contact_key=first['contact_key']
                conversation=_find_conversation(db,tenant_id,instance_id,contact_key)
                if conversation is None:
                    conversation=Conversation(id=str(uuid.uuid4()),tenant_id=tenant_id,
                        instance_id=instance_id,contact_key=contact_key,
                        contact_name=(first.get('contact_name') or '')[:180],status='historical',
                        history_only=True,consent_status='unknown')
                    db.add(conversation);db.flush()
                elif not conversation.contact_name and first.get('contact_name'):
                    conversation.contact_name=first['contact_name'][:180]
                _attach_alias(db,tenant_id,instance_id,conversation,contact_key)
                batch=HistoricalImportBatch(id=str(uuid.uuid4()),tenant_id=tenant_id,
                    source_sha256=source_hash,source_version=first['source_version'],
                    source_timezone=first['source_timezone'],message_count=len(rows))
                db.add(batch);db.flush()
                newest=None; newest_incoming=None
                for row in rows:
                    created=row['created_at_dt']
                    db.add(Message(id=str(uuid.uuid4()),tenant_id=tenant_id,
                        conversation_id=conversation.id,history_import_batch_id=batch.id,
                        history_source_ordinal=row['ordinal'],original_timestamp_text=row['original_timestamp_text'],
                        author_name=row.get('author_name'),author_kind=row['author_kind'],
                        direction=row['direction'],kind=row['kind'],content=row['content'],
                        status='historical',created_at=created))
                    newest=max(newest,created) if newest else created
                    if row['direction']=='incoming':
                        newest_incoming=max(newest_incoming,created) if newest_incoming else created
                if newest and (conversation.last_message_at is None or created_later(newest,conversation.last_message_at)):
                    conversation.last_message_at=newest
                if newest_incoming and (conversation.last_incoming_at is None or created_later(newest_incoming,conversation.last_incoming_at)):
                    conversation.last_incoming_at=newest_incoming
            db.flush()
            report['imported_messages']=sum(map(len,pending.values()))
            report['applied']=True
        return report
    finally:
        db.close()


def created_later(candidate, existing):
    if existing.tzinfo is None:
        existing=existing.replace(tzinfo=timezone.utc)
    return candidate > existing.astimezone(timezone.utc)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant-id',required=True)
    parser.add_argument('--instance-id',required=True)
    parser.add_argument('--apply',action='store_true',help='Grava o pacote; sem essa flag executa apenas dry-run.')
    args=parser.parse_args()
    try:
        result=import_history(sys.stdin,args.tenant_id,args.instance_id,apply=args.apply)
    except Exception as exc:
        message=str(exc)[:200] if isinstance(exc,ValueError) else 'Falha transacional; nenhum registro foi confirmado.'
        print(json.dumps({'applied':False,'error_class':type(exc).__name__,'error':message}))
        raise SystemExit(1)
    print(json.dumps(result))


if __name__=='__main__':
    main()
