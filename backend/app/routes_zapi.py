from datetime import datetime, timezone
import logging
import secrets

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.dependencies import CurrentUser, DbSession, TenantId
from app.models import Conversation, Message, OutboxMessage, User, ZapiInstance
from app.schemas import SendTextRequest, ZapiInstanceCreate
from app.security import callback_secret_matches, decrypt_secret, encrypt_secret, hash_callback_secret
from app.zapi_client import ZapiClient, ZapiError
from app.zapi_payload import classify, contact_key, contact_name, event_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Z-API"])


def _require_admin(user: User) -> None:
    if user.role not in {"platform_admin", "tenant_admin"}:
        raise HTTPException(status_code=403, detail="Ação restrita a administradores")


def _get_instance(db, tenant_id: str, internal_id: str) -> ZapiInstance:
    row = db.query(ZapiInstance).filter(ZapiInstance.id == internal_id, ZapiInstance.tenant_id == tenant_id, ZapiInstance.is_active.is_(True)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Instância não encontrada")
    return row


def _client(row: ZapiInstance) -> ZapiClient:
    return ZapiClient(row.instance_id, decrypt_secret(row.token_encrypted) or "", decrypt_secret(row.client_token_encrypted))


def _instance_read(row: ZapiInstance) -> dict:
    return {"id": row.id, "label": row.label, "instance_id": row.instance_id, "status": row.status, "webhook_configured": row.webhook_configured, "credentials_configured": True, "created_at": row.created_at.isoformat()}


@router.get("/zapi/instances")
def list_instances(db: DbSession, tenant_id: TenantId) -> list[dict]:
    rows = db.query(ZapiInstance).filter(ZapiInstance.tenant_id == tenant_id, ZapiInstance.is_active.is_(True)).order_by(ZapiInstance.created_at.desc()).all()
    return [_instance_read(row) for row in rows]


@router.post("/zapi/instances", status_code=201)
def create_instance(payload: ZapiInstanceCreate, request: Request, db: DbSession, tenant_id: TenantId, user: CurrentUser) -> dict:
    _require_admin(user)
    callback_token = secrets.token_urlsafe(36)
    row = ZapiInstance(
        tenant_id=tenant_id,
        label=payload.label.strip(),
        instance_id=payload.instance_id.strip(),
        token_encrypted=encrypt_secret(payload.token) or "",
        client_token_encrypted=encrypt_secret(payload.client_token),
        callback_token_hash=hash_callback_secret(callback_token),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Essa instância Z-API já está vinculada à plataforma") from exc
    db.refresh(row)

    public_base = settings.public_base_url
    if not public_base and request.url.scheme == "https":
        public_base = str(request.base_url).rstrip("/")
    callback_url = f"{public_base}/api/webhooks/zapi/{row.instance_id}/{callback_token}" if public_base.startswith("https://") else None
    webhook_configured = False
    callback_message = None
    if callback_url:
        try:
            _client(row).set_received_webhook(callback_url)
            webhook_configured = True
        except (ZapiError, ValueError):
            # Mostrar a URL uma única vez para configuração manual; segredos não são gravados nos logs.
            callback_message = "Não foi possível confirmar a configuração remota; a URL pode ser cadastrada manualmente no painel Z-API."
    row.webhook_configured = webhook_configured
    db.commit()
    result = _instance_read(row)
    result.update({"callback_url": callback_url if not webhook_configured else None, "webhook_configured": webhook_configured, "notice": callback_message or (None if callback_url else "Defina PUBLIC_BASE_URL HTTPS e configure o webhook antes de ativar a integração.")})
    return result


@router.post("/zapi/instances/{internal_id}/refresh-status")
def refresh_status(internal_id: str, db: DbSession, tenant_id: TenantId, user: CurrentUser) -> dict:
    row = _get_instance(db, tenant_id, internal_id)
    try:
        response = _client(row).status()
    except ZapiError as exc:
        row.status = "error"
        db.commit()
        raise HTTPException(status_code=502, detail=f"Falha ao consultar Z-API (HTTP {exc.status_code or 'rede'})") from exc
    row.status = "connected" if response.get("connected") is True else "disconnected"
    db.commit()
    return {"id": row.id, "status": row.status, "connected": response.get("connected") is True, "smartphone_connected": response.get("smartphoneConnected") is True}


@router.post("/zapi/instances/{internal_id}/send-text", status_code=202)
def send_text(internal_id: str, payload: SendTextRequest, db: DbSession, tenant_id: TenantId, user: CurrentUser) -> dict:
    row = _get_instance(db, tenant_id, internal_id)
    if user.role not in {"platform_admin", "tenant_admin", "operator"}:
        raise HTTPException(status_code=403, detail="Acesso negado")
    phone = payload.phone.strip()
    if "@" not in phone:
        phone = "".join(c for c in phone if c.isdigit())
    else:
        phone = phone.strip()
    if len(phone) < 5:
        raise HTTPException(status_code=422, detail="Telefone inválido")
    conversation = db.query(Conversation).filter(Conversation.tenant_id == tenant_id, Conversation.instance_id == row.id, Conversation.contact_key == phone).first()
    if conversation is None:
        conversation = Conversation(tenant_id=tenant_id, instance_id=row.id, contact_key=phone, contact_name="", status="open")
        db.add(conversation)
        db.flush()
    outbox = OutboxMessage(tenant_id=tenant_id, instance_id=row.id, conversation_id=conversation.id, idempotency_key=secrets.token_urlsafe(24), destination=phone, content=payload.message, status="dispatching", attempts=1)
    db.add(outbox)
    db.commit()
    db.refresh(outbox)
    try:
        remote = _client(row).send_text(phone, payload.message)
    except (ZapiError, ValueError) as exc:
        outbox.status = "failed"
        outbox.last_error = (str(exc) if isinstance(exc, ValueError) else f"Z-API HTTP {exc.status_code or 'rede'}")[:500]
        db.commit()
        raise HTTPException(status_code=502, detail="Falha ao enviar mensagem pela Z-API; consulte o estado da mensagem antes de repetir") from exc
    external_id = str(remote.get("messageId") or remote.get("zaapId") or remote.get("id") or "")[:180] or None
    outbox.status = "accepted"
    outbox.external_message_id = external_id
    db.add(Message(tenant_id=tenant_id, conversation_id=conversation.id, external_id=external_id, direction="outgoing", kind="text", content=payload.message, status="accepted"))
    conversation.last_message_at = datetime.now(timezone.utc)
    db.commit()
    return {"outbox_id": outbox.id, "message_id": external_id, "status": "accepted_by_api_not_delivery_confirmed"}


@router.delete("/zapi/instances/{internal_id}", status_code=204)
def deactivate_instance(internal_id: str, db: DbSession, tenant_id: TenantId, user: CurrentUser) -> None:
    _require_admin(user)
    row = _get_instance(db, tenant_id, internal_id)
    row.is_active = False
    row.status = "disabled"
    db.commit()


def _minimize_payload(payload: dict) -> dict:
    safe: dict = {}
    for key in ("instanceId", "messageId", "zaapId", "id", "phone", "fromMe", "momment", "status", "type", "isGroup", "senderName", "chatName", "senderLid", "participantPhone", "participantLid"):
        value = payload.get(key)
        if isinstance(value, (str, bool, int, float)) or value is None:
            safe[key] = value
    kind, content = classify(payload)
    safe["normalizedKind"] = kind
    if kind == "text":
        safe["normalizedText"] = content[:12000]
    return safe


@router.post("/webhooks/zapi/{instance_id}/{callback_token}", status_code=202)
async def receive_zapi_webhook(instance_id: str, callback_token: str, request: Request, db: DbSession) -> dict:
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > 1024 * 1024:
        raise HTTPException(status_code=413, detail="Webhook excede o tamanho permitido")
    body = await request.body()
    if len(body) > 1024 * 1024:
        raise HTTPException(status_code=413, detail="Webhook excede o tamanho permitido")
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Payload JSON inválido") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Payload deve ser um objeto JSON")
    row = db.query(ZapiInstance).filter(ZapiInstance.instance_id == instance_id, ZapiInstance.is_active.is_(True)).first()
    if row is None or not callback_secret_matches(row.callback_token_hash, callback_token):
        raise HTTPException(status_code=404, detail="Webhook não encontrado")
    payload_instance = payload.get("instanceId")
    if payload_instance and str(payload_instance) != row.instance_id:
        raise HTTPException(status_code=400, detail="Identificador de instância não confere")
    key = event_key(payload)
    event_type = str(payload.get("type") or "unknown")[:80]
    from app.models import WebhookEvent
    existing = db.query(WebhookEvent).filter(WebhookEvent.instance_id == row.id, WebhookEvent.event_key == key, WebhookEvent.event_type == event_type).first()
    if existing:
        if not existing.processed:
            try:
                from app.tasks import process_webhook_event
                process_webhook_event.delay(existing.id)
            except Exception:
                logger.warning("Evento Z-API %s ainda não processado; reenvio para worker falhou", existing.id)
        return {"accepted": True, "duplicate": True}
    event = WebhookEvent(tenant_id=row.tenant_id, instance_id=row.id, event_key=key, event_type=event_type, payload=_minimize_payload(payload))
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"accepted": True, "duplicate": True}
    db.refresh(event)
    try:
        from app.tasks import process_webhook_event
        process_webhook_event.delay(event.id)
    except Exception:
        # O evento continua persistido no banco; o retorno não revela o payload nem segredos.
        logger.warning("Evento Z-API %s persistido, mas não despachado; verificar worker/broker", event.id)
    return {"accepted": True, "duplicate": False}
