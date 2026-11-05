"""Durable outbound service. No automatic retry after an ambiguous external effect."""
from datetime import datetime, timedelta, timezone
import logging
import secrets
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.database import SessionLocal
from app.locks import tenant_guard
from app.models import Agent, Conversation, Message, OutboxMessage, ZapiInstance
from app.policy import sending_denial, advance_status
from app.security import decrypt_secret
from app.zapi_client import ZapiClient, ZapiError

logger = logging.getLogger(__name__)


def enqueue(db, instance, conversation, content, *, revision=None, idempotency_key=None):
    if instance.tenant_id != conversation.tenant_id or instance.id != conversation.instance_id:
        raise ValueError('Conversa não pertence à instância/empresa')
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
    db.add(row)
    try:
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
    if not settings.outbound_enabled:
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
                db.commit()
                return denial
            recent = db.query(func.count(OutboxMessage.id)).filter(
                OutboxMessage.instance_id == instance.id, OutboxMessage.tenant_id == row.tenant_id,
                OutboxMessage.attempts > 0, OutboxMessage.updated_at >= now - timedelta(minutes=1)).scalar()
            if recent >= instance.messages_per_minute:
                row.next_attempt_at = now + timedelta(seconds=60)
                db.commit()
                return 'rate_limited'
            row.status = 'dispatching'
            row.attempts += 1
            db.commit()  # Durable claim before external effect; session advisory lock remains held.
            try:
                remote = ZapiClient(instance.instance_id, decrypt_secret(instance.token_encrypted) or '',
                                    decrypt_secret(instance.client_token_encrypted)).send_text(row.destination, row.content)
            except (ZapiError, ValueError) as exc:
                row.last_error = f'Z-API HTTP {exc.status_code or "network"}' if isinstance(exc, ZapiError) else 'invalid_destination'
                # Even 429 is not replayed automatically without a verified no-effect contract.
                row.status = 'unknown' if isinstance(exc, ZapiError) and (exc.status_code == 0 or exc.status_code >= 500 or exc.status_code == 429) else 'failed'
                if isinstance(exc, ZapiError) and exc.status_code in {401, 403}:
                    instance.sending_enabled = False
                db.commit()
                return row.status
            remote_id = str(remote.get('messageId') or remote.get('id') or remote.get('zaapId') or '')[:180]
            if not remote_id:
                row.status, row.last_error = 'unknown', 'provider_returned_no_message_id'
                db.commit()
                return 'unknown'
            row.external_message_id = remote_id
            row.status, row.last_error = advance_status(row.status, 'accepted'), None
            if not db.query(Message).filter_by(tenant_id=row.tenant_id, conversation_id=conversation.id,
                                               external_id=remote_id, direction='outgoing').first():
                db.add(Message(tenant_id=row.tenant_id, conversation_id=conversation.id, external_id=remote_id,
                               direction='outgoing', kind='text', content=row.content, status='accepted'))
            conversation.last_message_at = datetime.now(timezone.utc)
            db.commit()
            return 'accepted'
    finally:
        db.close()
