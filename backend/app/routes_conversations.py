from fastapi import APIRouter, HTTPException

from app.dependencies import DbSession, TenantId
from app.models import Conversation, Message

router = APIRouter(prefix="/api/conversations", tags=["conversas"])


@router.get("")
def list_conversations(db: DbSession, tenant_id: TenantId) -> list[dict]:
    rows = db.query(Conversation).filter(Conversation.tenant_id == tenant_id).order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc()).limit(200).all()
    result = []
    for row in rows:
        last = db.query(Message).filter(Message.tenant_id == tenant_id, Message.conversation_id == row.id).order_by(Message.created_at.desc()).first()
        result.append({"id": row.id, "contact_key": row.contact_key, "contact_name": row.contact_name, "status": row.status, "last_message": last.content[:300] if last else "", "last_message_at": row.last_message_at.isoformat() if row.last_message_at else None})
    return result


@router.get("/{conversation_id}/messages")
def list_messages(conversation_id: str, db: DbSession, tenant_id: TenantId) -> list[dict]:
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id, Conversation.tenant_id == tenant_id).first()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    rows = db.query(Message).filter(Message.tenant_id == tenant_id, Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).limit(500).all()
    return [{"id": x.id, "external_id": x.external_id, "direction": x.direction, "kind": x.kind, "text": x.content, "status": x.status, "created_at": x.created_at.isoformat()} for x in rows]
