"""Memory review and last-decision inspection, always tenant-scoped."""
from fastapi import APIRouter, HTTPException

from app.dependencies import CurrentUser, DbSession, TenantId
from app.models import Conversation, LLMConfig, MemoryItem, ModelRun
from app.schemas import MemoryUpdate

router = APIRouter(prefix='/api', tags=['conversation-memory'])

DECISION_KEYS = ('intent', 'sentiment', 'stage', 'pending', 'next_best_action', 'decision_action')


def _memory_payload(row):
    return {'id': row.id, 'kind': row.kind, 'fact_key': row.fact_key,
            'content': row.content, 'approved': row.approved, 'source': row.source,
            'source_message_id': row.source_message_id, 'confidence': row.confidence,
            'created_at': row.created_at.isoformat() if row.created_at else None,
            'last_seen_at': row.last_seen_at.isoformat() if row.last_seen_at else None,
            'expires_at': row.expires_at.isoformat() if row.expires_at else None}


def _decision_payload(state):
    return {key: state.get(key) for key in DECISION_KEYS if key in state}


def _conversation(db, tenant_id, identifier):
    row = db.query(Conversation).filter_by(tenant_id=tenant_id, id=identifier).first()
    if not row:
        raise HTTPException(404, detail='Conversa não encontrada')
    return row


def _require_admin(user):
    if user.role not in {'platform_admin', 'tenant_admin'}:
        raise HTTPException(403, detail='Ação restrita a administradores')


@router.get('/conversations/{conversation_id}/memory')
def read_memory(conversation_id: str, db: DbSession, tenant_id: TenantId):
    row = _conversation(db, tenant_id, conversation_id)
    items = (db.query(MemoryItem)
             .filter_by(tenant_id=tenant_id, contact_key=row.contact_key)
             .order_by(MemoryItem.created_at.desc()).limit(100).all())
    state = row.context_state or {}
    return {'summary': state.get('summary') or '', 'pending': state.get('pending') or [],
            'items': [_memory_payload(item) for item in items]}


@router.get('/conversations/{conversation_id}/decision')
def read_decision(conversation_id: str, db: DbSession, tenant_id: TenantId):
    row = _conversation(db, tenant_id, conversation_id)
    payload = _decision_payload(row.context_state or {})
    last_run = (db.query(ModelRun)
                .filter_by(tenant_id=tenant_id, conversation_id=conversation_id)
                .order_by(ModelRun.created_at.desc(), ModelRun.id.desc()).first())
    config = (db.query(LLMConfig).filter_by(tenant_id=tenant_id, id=last_run.selected_config_id).first()
              if last_run and last_run.selected_config_id else None)
    payload['provider'] = config.provider if config else None
    payload['model'] = config.model if config else None
    return payload


@router.patch('/memory/{memory_id}')
def update_memory(memory_id: str, payload: MemoryUpdate, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    row = db.query(MemoryItem).filter_by(tenant_id=tenant_id, id=memory_id).first()
    if not row:
        raise HTTPException(404, detail='Memória não encontrada')
    if payload.approved is not None:
        if payload.approved and row.kind == 'business' and user.role not in {'platform_admin', 'tenant_admin'}:
            raise HTTPException(403, detail='Somente administrador aprova fato comercial')
        row.approved = payload.approved
    if payload.expires_at is not None:
        row.expires_at = payload.expires_at
    db.commit()
    return _memory_payload(row)


@router.delete('/memory/{memory_id}', status_code=204)
def delete_memory(memory_id: str, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    row = db.query(MemoryItem).filter_by(tenant_id=tenant_id, id=memory_id).first()
    if not row:
        raise HTTPException(404, detail='Memória não encontrada')
    if row.kind == 'business':
        _require_admin(user)
    db.delete(row)
    db.commit()
