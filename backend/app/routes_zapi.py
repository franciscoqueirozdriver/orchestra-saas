from app.control import serialized_mutation
from datetime import datetime, timezone, timedelta
import logging
import secrets

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.dependencies import CurrentUser, DbSession, TenantId
from app.models import Agent, Conversation, Message, OutboxMessage, User, ZapiInstance, InterventionRequest
from app.schemas import SendTextRequest, ZapiInstanceCreate, InstancePolicyUpdate, InterventionRoutingUpdate, InterventionGroupCreate, InterventionGroupConfirmation
from app.security import callback_secret_matches, decrypt_secret, encrypt_secret, hash_callback_secret
from app.transport import client_for, is_wame_provider
from app.wame_payload import is_wame_envelope, normalize_wame_events
from app.zapi_client import ZapiError
from app.zapi_payload import classify, contact_key, contact_name, event_key
from app.interventions import group_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Z-API"])


def _require_admin(user: User) -> None:
    if user.role not in {"platform_admin", "tenant_admin"}:
        raise HTTPException(status_code=403, detail="Ação restrita a administradores")


def _get_instance(db, tenant_id: str, internal_id: str) -> ZapiInstance:
    row = db.query(ZapiInstance).filter(ZapiInstance.id == internal_id, ZapiInstance.tenant_id == tenant_id, ZapiInstance.is_active.is_(True)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Conexão não encontrada")
    return row


def _client(row: ZapiInstance):
    return client_for(row)


def _connection_profile(provider: str) -> dict:
    profiles = {
        "zapi": {"connection_label": "Z-API · API não oficial (QR Code)", "can_create_group": True},
        "wame": {"connection_label": "WAME", "can_create_group": True},
        "wame_qr": {"connection_label": "WAME · API não oficial (QR Code)", "can_create_group": True},
        "wame_official": {"connection_label": "WAME · API oficial", "can_create_group": True},
    }
    return profiles.get(provider, {"connection_label": "Conexão WhatsApp", "can_create_group": False})


def _instance_read(row: ZapiInstance) -> dict:
    profile = _connection_profile(row.provider)
    return {"id": row.id, "provider": row.provider, "connection_label": profile["connection_label"], "can_create_group": profile["can_create_group"], "label": row.label, "instance_id": row.instance_id, "api_base_url": row.api_base_url, "status": row.status, "agent_id":row.agent_id, "global_sending_enabled":settings.outbound_enabled, "sending_enabled":row.sending_enabled, "messages_per_minute":row.messages_per_minute, "webhook_configured": row.webhook_configured, "credentials_configured": True, "created_at": row.created_at.isoformat()}


@router.get("/zapi/instances")
def list_instances(db: DbSession, tenant_id: TenantId) -> list[dict]:
    rows = db.query(ZapiInstance).filter(ZapiInstance.tenant_id == tenant_id, ZapiInstance.is_active.is_(True)).order_by(ZapiInstance.created_at.desc()).all()
    return [_instance_read(row) for row in rows]


@router.post("/zapi/instances", status_code=201)
@serialized_mutation
def create_instance(payload: ZapiInstanceCreate, request: Request, db: DbSession, tenant_id: TenantId, user: CurrentUser) -> dict:
    _require_admin(user)
    callback_token = secrets.token_urlsafe(36)
    row = ZapiInstance(
        tenant_id=tenant_id,
        provider=payload.provider,
        label=payload.label.strip(),
        instance_id=payload.instance_id.strip(),
        api_base_url=payload.api_base_url,
        token_encrypted=encrypt_secret(payload.token) or "",
        client_token_encrypted=encrypt_secret(payload.client_token),
        callback_token_hash=hash_callback_secret(callback_token),
        callback_token_encrypted=encrypt_secret(callback_token),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Essa conexão já está vinculada à plataforma") from exc
    db.refresh(row)

    public_base = settings.public_base_url
    if not public_base and request.url.scheme == "https":
        public_base = str(request.base_url).rstrip("/")
    callback_url = f"{public_base}/api/webhooks/zapi/{row.instance_id}/{callback_token}" if public_base.startswith("https://") else None
    webhook_configured = False
    callback_message = None
    if callback_url:
        try:
            _client(row).configure_webhooks(callback_url)
            webhook_configured = True
        except (ZapiError, ValueError):
            # Mostrar a URL uma única vez para configuração manual; segredos não são gravados nos logs.
            callback_message = "Não foi possível confirmar a configuração remota; a URL pode ser cadastrada manualmente no painel do provedor."
    row.webhook_configured = webhook_configured
    db.commit()
    result = _instance_read(row)
    result.update({"callback_url": callback_url if not webhook_configured else None, "webhook_configured": webhook_configured, "notice": callback_message or (None if callback_url else "Defina PUBLIC_BASE_URL HTTPS e configure o webhook antes de ativar a integração.")})
    return result


@router.post("/zapi/instances/{internal_id}/refresh-status")
@serialized_mutation
def refresh_status(internal_id: str, db: DbSession, tenant_id: TenantId, user: CurrentUser) -> dict:
    row = _get_instance(db, tenant_id, internal_id)
    try:
        response = _client(row).status()
    except ZapiError as exc:
        row.status = "error"
        db.commit()
        raise HTTPException(status_code=502, detail=f"Falha ao consultar a conexão (HTTP {exc.status_code or 'rede'})") from exc
    row.status = "connected" if response.get("connected") is True else "disconnected"
    db.commit()
    return {"id": row.id, "status": row.status, "agent_id":row.agent_id, "global_sending_enabled":settings.outbound_enabled, "sending_enabled":row.sending_enabled, "messages_per_minute":row.messages_per_minute, "connected": response.get("connected") is True, "smartphone_connected": response.get("smartphoneConnected") is True}


@router.post("/zapi/instances/{internal_id}/send-text", status_code=202)
@serialized_mutation
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
    from app.policy import sending_denial
    from app.outbox import enqueue
    denial = sending_denial(row, conversation, allow_human=True)
    if denial: raise HTTPException(409, detail=denial)
    try:
        conversation.status = "human"
        outbox = enqueue(db, row, conversation, payload.message, idempotency_key=payload.idempotency_key,author_kind='operator',operator_id=user.id)
    except ValueError as exc: raise HTTPException(409, detail=str(exc)) from exc
    return {"outbox_id":outbox.id,"status":outbox.status}



@router.delete("/zapi/instances/{internal_id}", status_code=204)
@serialized_mutation
def deactivate_instance(internal_id: str, db: DbSession, tenant_id: TenantId, user: CurrentUser) -> None:
    _require_admin(user)
    row = _get_instance(db, tenant_id, internal_id)
    row.is_active = False
    row.status = "disabled"
    db.commit()


def _minimize_payload(payload: dict) -> dict:
    safe: dict = {}
    for key in ("instanceId", "messageId", "zaapId", "id", "phone", "fromMe", "momment", "status", "type", "isGroup", "senderName", "chatName", "senderLid", "participantPhone", "participantLid", "chatLid", "connected", "disconnected"):

        value = payload.get(key)
        if isinstance(value, (str, bool, int, float)) or value is None:
            safe[key] = value
    if isinstance(payload.get("ids"), list):
        safe["ids"] = [str(x)[:180] for x in payload["ids"][:1000] if isinstance(x, (str, int))]
    if payload.get("error"):
        safe["error"] = True  # Do not persist remote error text.
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
    accepted = row is not None and callback_secret_matches(row.callback_token_hash, callback_token)
    if row is not None and not accepted and row.callback_previous_hash and row.callback_previous_until:
        accepted = row.callback_previous_until > datetime.now(timezone.utc) and callback_secret_matches(row.callback_previous_hash, callback_token)
    if not accepted:
        raise HTTPException(status_code=404, detail="Webhook não encontrado")
    if is_wame_envelope(payload):
        if not is_wame_provider(row.provider):
            raise HTTPException(status_code=400, detail="Identificador de instância não confere")
        events = normalize_wame_events(payload)
        if not events:
            return {"accepted": True, "duplicate": False}
        stored = [_accept_event(db, row, item) for item in events]
        return {"accepted": True, "duplicate": all(item["duplicate"] for item in stored)}
    if is_wame_provider(row.provider):
        raise HTTPException(status_code=422, detail="Evento não reconhecido para esta conexão")
    payload_instance = payload.get("instanceId")
    if payload_instance and str(payload_instance) != row.instance_id:
        raise HTTPException(status_code=400, detail="Identificador de instância não confere")
    return _accept_event(db, row, payload)


def _accept_event(db, row: ZapiInstance, payload: dict) -> dict:
    if payload.get('type') == 'MessageStatusCallback':
        if not isinstance(payload.get('ids'), list) or not payload['ids'] or len(payload['ids']) > 1000 or any(not isinstance(i, (str, int)) or isinstance(i, bool) or len(str(i)) > 180 for i in payload['ids']):
            raise HTTPException(422, detail='Callback de status requer ids válidos')
        if payload.get('status') not in {'SENT', 'RECEIVED', 'READ', 'READ_BY_ME', 'PLAYED'}:
            raise HTTPException(422, detail='Status de mensagem não reconhecido')
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
                logger.warning("Evento de conexão %s ainda não processado; reenvio para worker falhou", existing.id)
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
        logger.warning("Evento de conexão %s persistido, mas não despachado; verificar worker/broker", event.id)
    return {"accepted": True, "duplicate": False}


@router.patch("/zapi/instances/{internal_id}/policy")
@serialized_mutation
def update_instance_policy(internal_id: str, payload: InstancePolicyUpdate, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    _require_admin(user)
    row = _get_instance(db, tenant_id, internal_id)
    changes = payload.model_dump(exclude_unset=True)
    if any(value is None for key, value in changes.items() if key != 'agent_id'):
        raise HTTPException(422, detail='Políticas não podem ser nulas')
    agent_id = changes.get('agent_id')
    if agent_id and not db.query(Agent).filter_by(id=agent_id, tenant_id=tenant_id).first():
        raise HTTPException(422, detail='Agente não pertence à empresa')
    for field, value in changes.items():
        setattr(row, field, value)
    db.commit()
    return _instance_read(row)


@router.post('/zapi/instances/{internal_id}/webhooks')
@serialized_mutation
def configure_instance_webhooks(internal_id: str, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    _require_admin(user)
    row = _get_instance(db, tenant_id, internal_id)
    if not settings.public_base_url:
        raise HTTPException(409, detail='Defina a origem pública HTTPS')
    token = decrypt_secret(row.callback_token_encrypted)
    if not token:
        token = secrets.token_urlsafe(36)
        row.callback_previous_hash = row.callback_token_hash
        row.callback_previous_until = datetime.now(timezone.utc) + timedelta(minutes=10)
        row.callback_token_hash = hash_callback_secret(token)
        row.callback_token_encrypted = encrypt_secret(token)
        db.commit()
    url = f'{settings.public_base_url}/api/webhooks/zapi/{row.instance_id}/{token}'
    try:
        _client(row).configure_webhooks(url)
    except (ZapiError, ValueError):
        row.webhook_configured = False
        db.commit()
        return {'configured': False, 'notice': 'Configuração não confirmada. Tente novamente; a mesma URL será reutilizada.'}
    row.webhook_configured = True
    db.commit()
    return {'configured': True}


def _intervention_route_read(row):
    profile = _connection_profile(row.provider)
    return {'instance_id':row.id,'provider':row.provider,
        'connection_label':profile['connection_label'],'can_create_group':profile['can_create_group'],
        'group_id':row.intervention_group_id,
        'staff_phones':row.intervention_staff_phones or [],
        'webhook_configured':row.webhook_configured,
        'validation_status':row.intervention_group_validation,
        'test_sent_at':row.intervention_group_tested_at.isoformat() if row.intervention_group_tested_at else None,
        'validated_at':row.intervention_group_validated_at.isoformat() if row.intervention_group_validated_at else None,
        'ready':row.intervention_group_validation=='validated' and bool(row.intervention_group_id) and bool(row.intervention_staff_phones) and row.webhook_configured}


@router.get('/zapi/instances/{internal_id}/intervention-routing')
def get_intervention_routing(internal_id: str, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    _require_admin(user)
    return _intervention_route_read(_get_instance(db,tenant_id,internal_id))


@router.put('/zapi/instances/{internal_id}/intervention-routing')
def update_intervention_routing(internal_id: str, payload: InterventionRoutingUpdate, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    from app.locks import tenant_guard
    _require_admin(user)
    with tenant_guard(tenant_id):
        row=_get_instance(db,tenant_id,internal_id)
        changed=(row.intervention_group_id!=payload.group_id.strip() or
                 row.intervention_staff_phones!=payload.staff_phones)
        row.intervention_group_id=payload.group_id.strip()
        row.intervention_staff_phones=payload.staff_phones
        if changed:
            row.intervention_group_validation='pending'
            row.intervention_group_tested_at=None
            row.intervention_group_validated_at=None
            db.query(InterventionRequest).filter(
                InterventionRequest.instance_id==row.id,
                InterventionRequest.status=='awaiting_claim').update(
                    {'status':'setup_required','notification_status':'cancelled'},synchronize_session=False)
        db.commit()
        return _intervention_route_read(row)


@router.post('/zapi/instances/{internal_id}/intervention-routing/create-group')
def create_intervention_group(internal_id: str, payload: InterventionGroupCreate, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    from app.locks import tenant_guard
    _require_admin(user)
    if not payload.confirmed_not_connected_number:
        raise HTTPException(422,detail='Confirme que a lista não inclui o número conectado a esta conexão')
    with tenant_guard(tenant_id):
        row=_get_instance(db,tenant_id,internal_id)
        if not _connection_profile(row.provider)['can_create_group']:
            raise HTTPException(409,detail='Esta conexão não oferece criação de grupo. Cadastre o identificador do grupo criado no WhatsApp.')
        if not settings.outbound_enabled or not row.sending_enabled:
            raise HTTPException(409,detail='O envio está pausado. Libere o envio global e desta conexão antes de criar o grupo.')
        try:
            result=_client(row).create_group(payload.group_name,payload.phones,auto_invite=payload.auto_invite)
        except (ZapiError,ValueError) as exc:
            raise HTTPException(502,detail='O provedor não confirmou a criação do grupo. Confira o WhatsApp antes de tentar novamente.') from exc
        group_id=str(result.get('phone') or '').strip()
        invitation_link=str(result.get('invitationLink') or '')
        if not group_id or len(group_id)>240 or not all(ch.isalnum() or ch in '@._-' for ch in group_id):
            raise HTTPException(502,detail='O provedor não retornou um identificador reconhecível. Confira se o grupo foi criado antes de repetir a ação.')
        row.intervention_group_id=group_id
        row.intervention_staff_phones=payload.phones
        row.intervention_group_validation='pending'
        row.intervention_group_tested_at=None
        row.intervention_group_validated_at=None
        db.query(InterventionRequest).filter(
            InterventionRequest.instance_id==row.id,
            InterventionRequest.status=='awaiting_claim').update(
                {'status':'setup_required','notification_status':'cancelled'},synchronize_session=False)
        db.commit()
        # The invitation link is returned only to the initiating administrator; never persist or log it.
        return {'group_id':group_id,'invitation_link':invitation_link or None,
            'validation_status':'pending','staff_phones':row.intervention_staff_phones}


@router.post('/zapi/instances/{internal_id}/intervention-routing/test')
def test_intervention_group(internal_id: str, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    from app.locks import tenant_guard
    _require_admin(user)
    with tenant_guard(tenant_id):
        row=_get_instance(db,tenant_id,internal_id)
        if not row.intervention_group_id or not row.intervention_staff_phones:
            raise HTTPException(409,detail='Cadastre o grupo e ao menos um atendente antes de enviar o teste')
        if not row.webhook_configured:
            raise HTTPException(409,detail='Configure e confirme o callback de mensagens recebidas antes do teste do grupo')
        if not settings.outbound_enabled or not row.sending_enabled:
            raise HTTPException(409,detail='O envio está pausado. Libere o envio global e desta conexão antes do teste explícito.')
        try:
            group_client(row).send_text(row.intervention_group_id,
                'Teste de configuração do diBBerDesk. Se esta mensagem chegou ao grupo correto, volte à plataforma e confirme o recebimento.')
        except (ZapiError,ValueError) as exc:
            row.intervention_group_validation='pending'
            db.commit()
            raise HTTPException(502,detail='Não foi possível enviar o teste ao grupo. Confira o identificador e tente novamente.') from exc
        row.intervention_group_validation='test_sent'
        row.intervention_group_tested_at=datetime.now(timezone.utc)
        row.intervention_group_validated_at=None
        db.commit()
        return _intervention_route_read(row)


@router.post('/zapi/instances/{internal_id}/intervention-routing/confirm')
def confirm_intervention_group(internal_id: str, payload: InterventionGroupConfirmation, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    from app.locks import tenant_guard
    _require_admin(user)
    if not payload.confirmed_received:
        raise HTTPException(422,detail='Confirme que a mensagem de teste foi recebida no grupo correto')
    with tenant_guard(tenant_id):
        row=_get_instance(db,tenant_id,internal_id)
        if row.intervention_group_validation!='test_sent' or not row.intervention_group_tested_at:
            raise HTTPException(409,detail='Envie e confira a mensagem de teste antes de validar o grupo')
        row.intervention_group_validation='validated'
        row.intervention_group_validated_at=datetime.now(timezone.utc)
        db.commit()
        return _intervention_route_read(row)
