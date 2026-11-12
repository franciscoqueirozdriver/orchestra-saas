from fastapi import APIRouter, HTTPException

from app.dependencies import CurrentUser, DbSession, TenantId
from app.control import serialized_mutation
from app.schemas import ConversationConsentUpdate, ConversationPolicyUpdate
from app.models import Agent, Conversation, InterventionRequest, Message, ModelRun, WebhookEvent, ZapiInstance
from app.outbound_control import outbound_status
from app.policy import sending_denial

router = APIRouter(prefix="/api/conversations", tags=["conversas"])


@router.get("")
def list_conversations(db: DbSession, tenant_id: TenantId) -> list[dict]:
    rows = db.query(Conversation).filter(Conversation.tenant_id == tenant_id).order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc()).limit(200).all()
    result = []
    for row in rows:
        last = db.query(Message).filter(Message.tenant_id == tenant_id, Message.conversation_id == row.id).order_by(Message.created_at.desc()).first()
        result.append({"id": row.id, "contact_key": row.contact_key, "contact_name": row.contact_name, "history_only": row.history_only, "status": row.status, "pause_reason": row.pause_reason, "revision": row.revision, "last_direction": last.direction if last else None, "last_author_kind": last.author_kind if last else None, "last_message": last.content[:300] if last else "", "last_message_at": row.last_message_at.isoformat() if row.last_message_at else None})
    return result


@router.get("/{conversation_id}/messages")
def list_messages(conversation_id: str, db: DbSession, tenant_id: TenantId) -> list[dict]:
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id, Conversation.tenant_id == tenant_id).first()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    rows = db.query(Message).filter(Message.tenant_id == tenant_id, Message.conversation_id == conversation_id).order_by(Message.created_at.desc(),Message.history_import_batch_id.desc().nullslast(),Message.history_source_ordinal.desc().nullslast(),Message.id.desc()).limit(500).all()
    rows.reverse()
    return [{"id": x.id, "external_id": x.external_id, "direction": x.direction, "author_kind": x.author_kind, "author_name": x.author_name, "is_historical": x.history_import_batch_id is not None, "kind": x.kind, "text": x.content, "status": x.status, "created_at": x.created_at.isoformat(), "original_timestamp_text": x.original_timestamp_text} for x in rows]


@router.patch("/{conversation_id}/policy")
@serialized_mutation
def update_policy(conversation_id: str, payload: ConversationPolicyUpdate, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    if user.role not in {'platform_admin', 'tenant_admin'}:
        raise HTTPException(403, detail='Ação restrita a administradores')
    row = db.query(Conversation).filter_by(id=conversation_id, tenant_id=tenant_id).first()
    if not row:
        raise HTTPException(404, detail='Conversa não encontrada')
    if payload.consent_status == 'granted' and not payload.consent_evidence.strip():
        raise HTTPException(422, detail='Registre a evidência da permissão antes de liberar o contato')
    row.status, row.consent_status = payload.status, payload.consent_status
    row.consent_evidence = payload.consent_evidence.strip()
    row.opted_out = payload.consent_status == 'denied'
    db.commit()
    return {'id': row.id, 'status': row.status, 'consent_status': row.consent_status, 'opted_out': row.opted_out}


@router.post("/{conversation_id}/consent")
def record_contact_consent(conversation_id: str, payload: ConversationConsentUpdate, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    if user.role not in {'platform_admin', 'tenant_admin'}:
        raise HTTPException(status_code=403, detail='Ação restrita a administradores')
    evidence=payload.evidence.strip()
    if len(evidence)<5:
        raise HTTPException(status_code=422,detail='Registre evidência suficiente da nova autorização')
    with tenant_guard(tenant_id):
        db.expire_all();row=_conversation(db,tenant_id,conversation_id)
        row.consent_status='granted';row.consent_evidence=evidence;row.opted_out=False
        invalidate(db,row,'contact_consent_updated')
        db.commit()
    return {'id':row.id,'status':row.status,'consent_status':row.consent_status,'opted_out':row.opted_out,'revision':row.revision}


from app.schemas import ConversationActionRequest, ConversationSendRequest
from app.models import ConversationAction, OutboxMessage, OutboxPart, ZapiInstance
from app.locks import tenant_guard
from app.conversation.service import action, invalidate


def _operator(user):
    if user.role not in {'platform_admin','tenant_admin','operator'}:
        raise HTTPException(403,detail='Ação restrita à equipe autorizada')


def _conversation(db, tenant_id, identifier):
    row=db.query(Conversation).filter_by(tenant_id=tenant_id,id=identifier).first()
    if not row:raise HTTPException(404,detail='Conversa não encontrada')
    return row


def _state(row):
    return {'id':row.id,'status':row.status,'pause_reason':row.pause_reason,'revision':row.revision,
            'consent_status':row.consent_status,'opted_out':row.opted_out}


@router.get('/{conversation_id}/state')
def conversation_state(conversation_id: str, db: DbSession, tenant_id: TenantId):
    row=_conversation(db,tenant_id,conversation_id)
    instance=db.query(ZapiInstance).filter_by(id=row.instance_id,tenant_id=tenant_id).first()
    agent=db.query(Agent).filter_by(id=instance.agent_id,tenant_id=tenant_id).first() if instance and instance.agent_id else None
    last_message=db.query(Message).filter_by(tenant_id=tenant_id,conversation_id=row.id).order_by(Message.created_at.desc(),Message.id.desc()).first()
    last_event=db.query(WebhookEvent).filter_by(tenant_id=tenant_id,instance_id=row.instance_id,event_key=last_message.external_id,event_type='ReceivedCallback').first() if last_message and last_message.external_id else None
    last_run=db.query(ModelRun).filter_by(tenant_id=tenant_id,conversation_id=row.id).order_by(ModelRun.created_at.desc(),ModelRun.id.desc()).first()
    last_intervention=db.query(InterventionRequest).filter_by(tenant_id=tenant_id,conversation_id=row.id).order_by(InterventionRequest.created_at.desc(),InterventionRequest.id.desc()).first()
    pending=db.query(OutboxMessage).filter_by(tenant_id=tenant_id,conversation_id=row.id).order_by(OutboxMessage.created_at.desc()).limit(20).all()
    denial=sending_denial(instance,row)
    global_control=outbound_status()
    if not global_control['enabled']:
        global_block='global_outbound_disabled'
    else:
        global_block=None
    if not instance or not instance.is_active:
        connection_block='connection_inactive'
    elif instance.status!='connected':
        connection_block='connection_disconnected'
    elif not instance.sending_enabled:
        connection_block='connection_sending_paused'
    elif not instance.webhook_configured:
        connection_block='webhook_not_configured'
    else:
        connection_block=None
    if not instance or not instance.agent_id:
        agent_block='agent_unassigned'
    elif not agent or not agent.enabled:
        agent_block='agent_disabled'
    elif not agent.auto_reply_enabled:
        agent_block='auto_reply_disabled'
    else:
        agent_block=None
    blockers=[x for x in (global_block,connection_block,agent_block,denial) if x]
    processing={'webhook':{'processed':last_event.processed,'attempts':last_event.attempts,'error':last_event.processing_error,'received_at':last_event.received_at.isoformat()} if last_event else None,
                'model':{'status':last_run.status,'attempts':[{'provider':a.get('provider'),'model':a.get('model'),'result':a.get('result'),'http_status':a.get('http_status'),**({'failure_stage':a['failure_stage']} if a.get('failure_stage') else {})} for a in (last_run.attempts or []) if isinstance(a,dict)]} if last_run else None,
                'intervention':{'reason':last_intervention.reason,'status':last_intervention.status,'notification_status':last_intervention.notification_status,'created_at':last_intervention.created_at.isoformat()} if last_intervention else None}
    return {**_state(row),
            'controls':{'global':global_control,
                'connection':{'id':instance.id,'label':instance.label,'active':instance.is_active,'status':instance.status,'sending_enabled':instance.sending_enabled,'webhook_configured':instance.webhook_configured} if instance else None,
                'agent':{'id':agent.id,'name':agent.name,'enabled':agent.enabled,'auto_reply_enabled':agent.auto_reply_enabled} if agent else None,
                'policy_denial':denial,'blockers':list(dict.fromkeys(blockers)),
                'last_incoming_at':row.last_incoming_at.isoformat() if row.last_incoming_at else None,
                'last_message_direction':last_message.direction if last_message else None,
                'last_message_author':last_message.author_kind if last_message else None,
                'processing':processing},
            'outbox':[{'id':p.id,'status':p.status,'last_error':p.last_error,
            'parts':[{'ordinal':part.ordinal,'status':part.status} for part in db.query(OutboxPart).filter_by(tenant_id=tenant_id,outbox_id=p.id).order_by(OutboxPart.ordinal)]} for p in pending]}


def _act(identifier,payload,db,tenant_id,user,mode):
    _operator(user)
    with tenant_guard(tenant_id):
        db.expire_all();row=_conversation(db,tenant_id,identifier)
        if row.revision!=payload.expected_revision:raise HTTPException(409,detail='A conversa mudou; atualize antes de continuar')
        action(db,row,mode,user.id)
        db.commit()
        return _state(row)


@router.post('/{conversation_id}/takeover')
def takeover(conversation_id: str,payload: ConversationActionRequest,db: DbSession,tenant_id: TenantId,user: CurrentUser):
    return _act(conversation_id,payload,db,tenant_id,user,'takeover')


@router.post('/{conversation_id}/resume')
def resume(conversation_id: str,payload: ConversationActionRequest,db: DbSession,tenant_id: TenantId,user: CurrentUser):
    return _act(conversation_id,payload,db,tenant_id,user,'resume')


@router.post('/{conversation_id}/cancel')
def cancel(conversation_id: str,payload: ConversationActionRequest,db: DbSession,tenant_id: TenantId,user: CurrentUser):
    return _act(conversation_id,payload,db,tenant_id,user,'cancel')


@router.post('/{conversation_id}/messages',status_code=202)
def send_human(conversation_id: str,payload: ConversationSendRequest,db: DbSession,tenant_id: TenantId,user: CurrentUser):
    from app.outbox import enqueue
    from app.policy import sending_denial
    _operator(user)
    with tenant_guard(tenant_id):
        db.expire_all();row=_conversation(db,tenant_id,conversation_id)
        existing=db.query(OutboxMessage).filter_by(tenant_id=tenant_id,idempotency_key=payload.idempotency_key).first()
        if existing:
            if existing.conversation_id!=row.id or existing.content!=payload.message or existing.operator_id!=user.id:
                raise HTTPException(409,detail='Chave de idempotência em uso')
            return {'id':existing.id,'status':existing.status}
        if row.revision!=payload.expected_revision:raise HTTPException(409,detail='A conversa mudou; atualize antes de enviar')
        instance=db.query(ZapiInstance).filter_by(tenant_id=tenant_id,id=row.instance_id).first()
        if sending_denial(instance,row,allow_human=True):raise HTTPException(409,detail='Envio bloqueado pela política do contato ou conexão')
        action(db,row,'takeover',user.id)
        queued=enqueue(db,instance,row,payload.message,idempotency_key=payload.idempotency_key,author_kind='operator',operator_id=user.id)
        return {'id':queued.id,'status':queued.status}
