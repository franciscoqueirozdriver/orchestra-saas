"""Caller must own the tenant guard; all invalidation is conversation-scoped."""
import logging
from app.models import Conversation, ConversationAction, OutboxMessage, OutboxPart, Agent, ZapiInstance
from datetime import datetime,timezone,timedelta
from app.schemas import ConversationProfile

logger=logging.getLogger(__name__)


def profile_for(agent):
    return ConversationProfile.model_validate((agent.conversation_profile if agent else None) or {})


def invalidate(db, conversation, reason, *, include_manual=False):
    query=db.query(OutboxMessage).filter_by(tenant_id=conversation.tenant_id,conversation_id=conversation.id)
    if not include_manual:query=query.filter(OutboxMessage.response_revision.isnot(None))
    for parent in query.filter(OutboxMessage.status.in_(['pending','retry_wait'])).all():
        parent.status,parent.last_error='cancelled',reason
        cancelled=db.query(OutboxPart).filter_by(tenant_id=conversation.tenant_id,outbox_id=parent.id,status='pending').update({'status':'cancelled'},synchronize_session=False)
        if cancelled:
            logger.info('outbox_parts_cancelled tenant=%s conversation=%s reason=%s count=%s',
                        conversation.tenant_id,conversation.id,reason,cancelled)
    conversation.revision+=1
    conversation.response_attempts=0


def action(db, conversation, action_name, operator_id=None):
    invalidate(db,conversation,action_name,include_manual=True)
    if action_name=='resume':
        conversation.status='open';conversation.pause_reason=None
    else:
        conversation.status='human' if action_name in {'takeover','human_requested','intervention_requested'} else 'paused'
        conversation.pause_reason=action_name
    conversation.turn_started_at=None
    # Resume requires a fresh inbound; don't regenerate the question a human already answered.
    conversation.response_attempts=3
    conversation.context_state={};conversation.context_expires_at=None
    if action_name=='resume':
        instance=db.query(ZapiInstance).filter_by(id=conversation.instance_id,tenant_id=conversation.tenant_id).first()
        agent=db.query(Agent).filter_by(id=instance.agent_id,tenant_id=conversation.tenant_id).first() if instance and instance.agent_id else None
        conversation.context_expires_at=datetime.now(timezone.utc)+timedelta(minutes=profile_for(agent).context_minutes)
    db.add(ConversationAction(tenant_id=conversation.tenant_id,conversation_id=conversation.id,operator_id=operator_id,action=action_name,revision=conversation.revision))
    return conversation
