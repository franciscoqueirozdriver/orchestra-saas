"""Durable outbound service. No automatic retry after an ambiguous external effect."""
from datetime import datetime, timedelta, timezone
import logging
import secrets
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.database import SessionLocal
from app.locks import tenant_guard
from app.models import Agent, Conversation, Message, OutboxMessage, OutboxPart, ZapiInstance
from app.outbound_control import outbound_is_enabled
from app.policy import sending_denial, advance_status, STATUS_RANK
from app.transport import for_instance, TransportError

logger = logging.getLogger(__name__)


def enqueue(db, instance, conversation, content, *, revision=None, idempotency_key=None, author_kind="assistant", operator_id=None, parts=None, delivery_config=None):
    if instance.tenant_id != conversation.tenant_id or instance.id != conversation.instance_id:
        raise ValueError('Conversa não pertence à instância/empresa')
    if parts is not None and (not parts or ''.join(parts)!=content or len(parts)>80 or any(not p or len(p)>4000 for p in parts)):
        raise ValueError('Partes inválidas ou conteúdo divergente')
    key = idempotency_key or secrets.token_urlsafe(24)
    def existing_row():
        return db.query(OutboxMessage).filter(OutboxMessage.tenant_id == instance.tenant_id,
                                             OutboxMessage.idempotency_key == key).first()
    existing = existing_row()
    if existing:
        if (existing.instance_id, existing.conversation_id, existing.content) != (instance.id, conversation.id, content):
            raise ValueError('Chave de idempotência já usada para outra mensagem')
        return existing
    row = OutboxMessage(tenant_id=instance.tenant_id, instance_id=instance.id,
                        conversation_id=conversation.id, idempotency_key=key,
                        destination=conversation.contact_key, content=content,
                        response_revision=revision, status='pending', attempts=0)
    row.author_kind,row.operator_id=author_kind,operator_id
    row.delivery_config=delivery_config or {}
    db.add(row)
    try:
        db.flush()
        if parts is not None:
            db.add_all([OutboxPart(tenant_id=row.tenant_id,outbox_id=row.id,ordinal=i,content=p,status='pending') for i,p in enumerate(parts)])
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError('Mensagem já enfileirada ou chave de idempotência em uso') from None
    db.refresh(row)
    try:
        from app.tasks import dispatch_outbox
        dispatch_outbox.delay(row.id)
    except Exception:
        logger.warning('Outbox persistida; recuperação periódica necessária')
    return row


def dispatch(outbox_id):
    if not outbound_is_enabled():
        return 'outbound_disabled'
    db = SessionLocal()
    try:
        row = db.get(OutboxMessage, outbox_id)
        if not row:
            return 'ignored'
        with tenant_guard(row.tenant_id, blocking=False) as acquired:
            if not acquired:
                return 'busy'
            db.expire_all()
            row = db.get(OutboxMessage, outbox_id)
            if row.status not in {'pending', 'retry_wait'}:
                return 'ignored'
            now = datetime.now(timezone.utc)
            due = row.next_attempt_at
            if due and due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if due and due > now:
                return 'not_due'
            instance = db.query(ZapiInstance).filter_by(id=row.instance_id, tenant_id=row.tenant_id).first()
            conversation = db.query(Conversation).filter_by(id=row.conversation_id, tenant_id=row.tenant_id, instance_id=row.instance_id).first()
            denial = sending_denial(instance, conversation, now, allow_human=row.response_revision is None)
            if row.response_revision is not None and not denial:
                agent = db.query(Agent).filter_by(id=instance.agent_id, tenant_id=row.tenant_id, enabled=True, auto_reply_enabled=True).first()
                if not agent:
                    denial = 'agent_disabled_or_unassigned'
                elif row.response_revision != conversation.revision:
                    denial = 'stale_revision'
            if denial:
                row.status = 'cancelled' if denial == 'stale_revision' else 'blocked'
                row.last_error = denial
                db.query(OutboxPart).filter_by(tenant_id=row.tenant_id,outbox_id=row.id,status='pending').update({'status':row.status},synchronize_session=False)
                db.commit()
                return denial
            parts=db.query(OutboxPart).filter_by(tenant_id=row.tenant_id,outbox_id=row.id).order_by(OutboxPart.ordinal).all()
            part=next((p for p in parts if p.status=='pending'),None)
            if parts and not part:
                aggregate(db,row)
                db.commit()
                return 'ignored'
            recent = db.query(func.count(OutboxMessage.id)).filter(
                OutboxMessage.instance_id == instance.id, OutboxMessage.tenant_id == row.tenant_id,
                OutboxMessage.attempts > 0, OutboxMessage.updated_at >= now - timedelta(minutes=1),
                ~db.query(OutboxPart).filter(OutboxPart.outbox_id==OutboxMessage.id,OutboxPart.tenant_id==OutboxMessage.tenant_id).exists()).scalar()
            recent += db.query(func.count(OutboxPart.id)).join(OutboxMessage,OutboxPart.outbox_id==OutboxMessage.id).filter(
                OutboxPart.tenant_id==row.tenant_id,OutboxMessage.instance_id==instance.id,OutboxPart.attempts>0,OutboxPart.updated_at>=now-timedelta(minutes=1)).scalar()
            if recent >= instance.messages_per_minute:
                row.next_attempt_at = now + timedelta(seconds=60)
                db.commit()
                return 'rate_limited'
            if part:
                if any(p.ordinal<part.ordinal and p.status not in STATUS_RANK for p in parts):
                    return 'previous_part_unresolved'
                part.status='dispatching';part.attempts+=1
            row.status = 'dispatching'
            row.attempts += 1
            db.commit()  # Durable claim before external effect; session advisory lock remains held.
            try:
                transport=for_instance(instance)
                if part and part.ordinal==0 and row.delivery_config.get('presence'):
                    try:transport.composing(row.destination)
                    except Exception:pass  # Optional presence must never prevent text.
                receipt=transport.send_text(row.destination, part.content if part else row.content)
            except (TransportError, ValueError) as exc:
                row.last_error = f'transport HTTP {exc.status_code or "network"}' if isinstance(exc, TransportError) else 'invalid_destination'
                # Even 429 is not replayed automatically without a verified no-effect contract.
                row.status = 'unknown' if isinstance(exc, TransportError) and (exc.status_code == 0 or exc.status_code >= 500 or exc.status_code == 429) else 'failed'
                if isinstance(exc, TransportError) and exc.status_code in {401, 403}:
                    instance.sending_enabled = False
                if part:part.status=row.status
                db.commit()
                return row.status
            remote_id = receipt.message_id
            if not remote_id:
                row.status, row.last_error = 'unknown', 'provider_returned_no_message_id'
                if part:part.status='unknown'
                db.commit()
                return 'unknown'
            if part:
                part.external_message_id,part.status=remote_id,'accepted'
            row.external_message_id = row.external_message_id or remote_id
            row.status, row.last_error = advance_status(row.status, 'accepted'), None
            if not db.query(Message).filter_by(tenant_id=row.tenant_id, conversation_id=conversation.id,
                                               external_id=remote_id, direction='outgoing').first():
                db.add(Message(tenant_id=row.tenant_id, conversation_id=conversation.id, external_id=remote_id,
                               direction='outgoing', kind='text', content=part.content if part else row.content, status='accepted',author_kind=row.author_kind,operator_id=row.operator_id))
            conversation.last_message_at = datetime.now(timezone.utc)
            if parts:
                aggregate(db,row)
                if row.status=='pending':row.next_attempt_at=datetime.now(timezone.utc)+timedelta(seconds=int(row.delivery_config.get('delay',1)))
            db.commit()
            if parts and row.status=='pending':
                try:
                    from app.tasks import dispatch_outbox
                    dispatch_outbox.apply_async(args=[row.id],countdown=int(row.delivery_config.get('delay',1)))
                except Exception:logger.warning('Parte persistida; recuperação periódica necessária')
            return 'part_accepted' if parts and row.status=='pending' else 'accepted'
    finally:
        db.close()


def aggregate(db, parent):
    parts=db.query(OutboxPart).filter_by(tenant_id=parent.tenant_id,outbox_id=parent.id).all()
    if not parts:return
    states={p.status for p in parts}
    for state in ('unknown','failed','dispatching','pending','cancelled','blocked'):
        if state in states:
            parent.status=state
            return
    parent.status=min(states,key=lambda s:STATUS_RANK.get(s,-1))
