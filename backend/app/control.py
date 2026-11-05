"""Revision invalidation is shared by every supported configuration mutation."""
from sqlalchemy import select
from app.models import Conversation, OutboxMessage


def invalidate_conversations(db, tenant_id, instance_id=None):
    query = db.query(Conversation).filter(Conversation.tenant_id == tenant_id)
    if instance_id is not None:
        query = query.filter(Conversation.instance_id == instance_id)
    ids = select(Conversation.id).where(Conversation.tenant_id == tenant_id)
    if instance_id is not None:
        ids = ids.where(Conversation.instance_id == instance_id)
    db.query(OutboxMessage).filter(
        OutboxMessage.tenant_id == tenant_id, OutboxMessage.conversation_id.in_(ids),
        OutboxMessage.response_revision.isnot(None), OutboxMessage.status.in_(['pending', 'retry_wait'])
    ).update({OutboxMessage.status: 'cancelled', OutboxMessage.last_error: 'configuration_changed'}, synchronize_session=False)
    query.update({Conversation.revision: Conversation.revision + 1, Conversation.response_attempts: 0}, synchronize_session=False)


def serialized_mutation(fn):
    """Keep policy writes and their invalidation atomic relative to sends.

    Commits inside handlers are allowed: the session advisory guard is held until
    invalidation commits. All supported policy endpoints use this decorator.
    """
    from functools import wraps
    from inspect import signature
    from app.locks import tenant_guard
    sig = signature(fn)
    @wraps(fn)
    def guarded(*args, **kwargs):
        values = sig.bind(*args, **kwargs).arguments
        db, tenant_id = values['db'], values['tenant_id']
        with tenant_guard(tenant_id):
            db.expire_all()
            result = fn(*args, **kwargs)
            invalidate_conversations(db, tenant_id)
            db.commit()
            return result
    return guarded
