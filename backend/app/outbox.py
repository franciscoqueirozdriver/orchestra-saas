"""The only application service allowed to send WhatsApp messages."""
from datetime import datetime,timedelta,timezone
import secrets
from redis import Redis
from sqlalchemy import func
from app.config import settings
from app.database import SessionLocal
from app.models import Conversation,Message,OutboxMessage,ZapiInstance
from app.policy import sending_denial,advance_status
from app.security import decrypt_secret
from app.zapi_client import ZapiClient,ZapiError


def enqueue(db,instance,conversation,content,*,revision=None,idempotency_key=None):
    key=idempotency_key or secrets.token_urlsafe(24)
    existing=db.query(OutboxMessage).filter(OutboxMessage.tenant_id==instance.tenant_id,OutboxMessage.idempotency_key==key).first()
    if existing:
        if existing.instance_id!=instance.id or existing.conversation_id!=conversation.id or existing.content!=content:
            raise ValueError("Chave de idempotência já usada para outra mensagem")
        return existing
    row=OutboxMessage(tenant_id=instance.tenant_id,instance_id=instance.id,conversation_id=conversation.id,idempotency_key=key,destination=conversation.contact_key,content=content,response_revision=revision,status="pending",attempts=0)
    db.add(row);db.commit();db.refresh(row)
    try:
        from app.tasks import dispatch_outbox
        dispatch_outbox.delay(row.id)
    except Exception: pass  # Periodic recovery uses the durable pending row.
    return row


def dispatch(outbox_id):
    db=SessionLocal();cache=Redis.from_url(settings.redis_url,socket_connect_timeout=3,socket_timeout=3);lock=None
    try:
        row=db.get(OutboxMessage,outbox_id)
        if not row or row.status not in {"pending","retry_wait"}:return "ignored"
        lock=cache.lock("outbox-instance:"+row.instance_id,timeout=90,blocking_timeout=1)
        if not lock.acquire(blocking=True):return "busy"
        db.refresh(row)
        if row.status not in {"pending","retry_wait"}:return "ignored"
        now=datetime.now(timezone.utc)
        due=row.next_attempt_at
        if due and due.tzinfo is None:due=due.replace(tzinfo=timezone.utc)
        if due and due>now:return "not_due"
        instance=db.query(ZapiInstance).filter(ZapiInstance.id==row.instance_id,ZapiInstance.tenant_id==row.tenant_id).first()
        conversation=db.query(Conversation).filter(Conversation.id==row.conversation_id,Conversation.tenant_id==row.tenant_id,Conversation.instance_id==row.instance_id).first()
        denial=sending_denial(instance,conversation,now)
        if denial:
            row.status="blocked";row.last_error=denial;db.commit();return denial
        if row.response_revision is not None and row.response_revision!=conversation.revision:
            row.status="cancelled";row.last_error="stale_revision";db.commit();return "stale_revision"
        recent=db.query(func.count(OutboxMessage.id)).filter(OutboxMessage.instance_id==instance.id,OutboxMessage.tenant_id==row.tenant_id,OutboxMessage.attempts>0,OutboxMessage.updated_at>=now-timedelta(minutes=1)).scalar()
        if recent>=instance.messages_per_minute:
            row.next_attempt_at=now+timedelta(seconds=60);db.commit();return "rate_limited"
        row.status="dispatching";row.attempts+=1;db.commit()
        try:
            remote=ZapiClient(instance.instance_id,decrypt_secret(instance.token_encrypted) or "",decrypt_secret(instance.client_token_encrypted)).send_text(row.destination,row.content)
        except (ZapiError,ValueError) as exc:
            if isinstance(exc,ZapiError):
                row.last_error=f"Z-API HTTP {exc.status_code or 'network'}"
                # No assumed provider idempotency: ambiguous effects must never be blindly retried.
                if exc.status_code==429 and row.attempts<4:
                    row.status="retry_wait";row.next_attempt_at=now+timedelta(seconds=60*2**(row.attempts-1))
                else: row.status="unknown" if exc.status_code==0 or exc.status_code>=500 else "failed"
                if exc.status_code in {401,403}:instance.sending_enabled=False
            else:row.status="failed";row.last_error="invalid_destination"
            db.commit()
            failures=db.query(OutboxMessage.status).filter(OutboxMessage.instance_id==instance.id,OutboxMessage.attempts>0).order_by(OutboxMessage.updated_at.desc()).limit(3).all()
            if len(failures)==3 and all(x[0] in {"failed","unknown"} for x in failures):instance.sending_enabled=False;db.commit()
            return row.status
        remote_id=str(remote.get("messageId") or remote.get("id") or remote.get("zaapId") or "")[:180]
        if not remote_id:
            row.status="unknown";row.last_error="provider_returned_no_message_id";db.commit();return "unknown"
        row.external_message_id=remote_id;row.status=advance_status(row.status,"accepted");row.last_error=None
        db.add(Message(tenant_id=row.tenant_id,conversation_id=conversation.id,external_id=remote_id,direction="outgoing",kind="text",content=row.content,status="accepted"))
        conversation.last_message_at=datetime.now(timezone.utc);db.commit()
        return "accepted"
    finally:
        if lock:
            try:lock.release()
            except Exception:pass
        cache.close();db.close()
