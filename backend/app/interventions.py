"""Human intervention tickets and private, first-claim handoff."""
from datetime import datetime, timedelta, timezone
import re
import secrets

from app.models import InterventionRequest, Message, Conversation
from app.zapi_client import ZapiError
from app.config import settings
from app.outbound_control import outbound_is_enabled
from app.transport import client_for

CLAIM_COMMAND = re.compile(r'^\s*ASSUMINDO\s+(\d{6})\s*$', re.IGNORECASE)
TICKET_TTL_MINUTES = 60


def normalize_phone(value):
    digits = re.sub(r'\D', '', str(value or ''))
    return digits if 10 <= len(digits) <= 15 else ''


def group_client(instance):
    return client_for(instance)


def context_for(db, conversation, reason):
    rows = db.query(Message).filter_by(tenant_id=conversation.tenant_id,
        conversation_id=conversation.id).order_by(Message.created_at.desc(),Message.id.desc()).limit(12).all()
    rows.reverse()
    lines=[]
    for row in rows:
        author = row.author_name or {'user':'Cliente','assistant':'Agente','operator':'Equipe','system':'Sistema'}.get(row.author_kind,'Participante')
        lines.append(f'{author}: {row.content[:700]}')
    history='\n'.join(lines)[-3600:]
    contact = conversation.contact_name.strip() or conversation.contact_key
    state=(conversation.context_state or {}).get('sales_context') or {};facts=state.get('facts') or {};summary=[]
    for key,label in [('environment','Ambiente'),('objective','Objetivo'),('city','Cidade'),('address','Endereço'),('preferred_date','Data pretendida'),('preferred_time','Horário pretendido'),('receiver_name','Pessoa que receberá')]:
        item=facts.get(key)
        if isinstance(item,dict) and item.get('value'):summary.append(f'{label}: {str(item["value"])[:180]}')
    if state.get('channel_phone_status') in {'confirmed','alternate_authorized'}:
        item=facts.get('alternate_phone') if state['channel_phone_status']=='alternate_authorized' else facts.get('provider_phone')
        if isinstance(item,dict) and item.get('value'):summary.append('Telefone autorizado para retorno: '+str(item['value'])[:24])
    summary.extend(['Recebedor: '+str(state.get('receiver_status','unknown')),'Situação da visita: '+str(state.get('appointment_status','not_requested'))])
    sales='\nResumo comercial estruturado:\n'+'\n'.join(summary) if summary else ''
    return (f'Atendimento {reason}. Contato: {contact}. Identificador: {conversation.contact_key}.{sales}\n'
            f'Histórico recente (mais antigo primeiro):\n{history or "Sem mensagens anteriores registradas."}')[:3900]


def create_request(db, instance, conversation, reason):
    now=datetime.now(timezone.utc)
    db.query(InterventionRequest).filter(
        InterventionRequest.instance_id==instance.id,
        InterventionRequest.status.in_(['awaiting_claim','claimed','setup_required']),
        InterventionRequest.expires_at<=now).update({'status':'expired'},synchronize_session=False)
    ready=(instance.intervention_group_validation=='validated' and instance.intervention_group_id
           and bool(instance.intervention_staff_phones) and instance.webhook_configured)
    active_statuses=['awaiting_claim','claimed'] + ([] if ready else ['setup_required'])
    existing=db.query(InterventionRequest).filter(
        InterventionRequest.tenant_id==conversation.tenant_id,
        InterventionRequest.conversation_id==conversation.id,
        InterventionRequest.status.in_(active_statuses),
        InterventionRequest.expires_at>now).order_by(InterventionRequest.created_at.desc()).first()
    if existing:
        return existing, False
    for _ in range(5):
        code=f'{secrets.randbelow(900_000)+100_000:06d}'
        if db.query(InterventionRequest.id).filter(
            InterventionRequest.instance_id==instance.id,InterventionRequest.code==code,
            InterventionRequest.status.in_(['awaiting_claim','claimed','setup_required'])).first():
            continue
        row=InterventionRequest(tenant_id=conversation.tenant_id,instance_id=instance.id,
            conversation_id=conversation.id,code=code,reason=reason,
            status='awaiting_claim' if ready else 'setup_required',
            notification_status='pending' if ready else 'not_configured',
            expires_at=now+timedelta(minutes=TICKET_TTL_MINUTES))
        db.add(row)
        db.flush()
        return row, True
    raise RuntimeError('Não foi possível gerar um código de atendimento exclusivo')


def send_group_alert(db, instance, ticket):
    if ticket.status!='awaiting_claim' or instance.intervention_group_validation!='validated' or not instance.webhook_configured:
        return False
    if not instance.intervention_group_id or not instance.intervention_staff_phones:
        ticket.status='setup_required';ticket.notification_status='not_configured';db.commit();return False
    if not outbound_is_enabled() or not instance.sending_enabled:
        ticket.notification_status='blocked';db.commit();return False
    ticket.notification_status='dispatching'
    db.commit()
    try:
        group_client(instance).send_text(instance.intervention_group_id,
            f'Intervenção humana necessária. Atendimento {ticket.code}. '
            f'Responda em privado ao agente: ASSUMINDO {ticket.code}')
        ticket.notification_status='sent'
        ticket.status='awaiting_claim'
        db.commit()
        return True
    except (ZapiError,ValueError) as exc:
        ticket.notification_status=('unknown' if isinstance(exc,ZapiError) and
            (exc.status_code==0 or exc.status_code>=500 or exc.status_code==429) else 'failed')
        db.commit()
        return False


def private_claim(db, instance, payload):
    """Consume only an exact ASSUMINDO code from a private inbound WhatsApp message."""
    text=payload.get('normalizedText')
    if not isinstance(text,str):
        text=(payload.get('text') or {}).get('message') if isinstance(payload.get('text'),dict) else ''
    match=CLAIM_COMMAND.fullmatch(text or '')
    if not match:
        return None
    phone=normalize_phone(payload.get('phone') or payload.get('senderLid'))
    code=match.group(1)
    if not phone or phone not in {normalize_phone(x) for x in (instance.intervention_staff_phones or [])}:
        return {'status':'unauthorized','phone':phone}
    if not outbound_is_enabled() or not instance.sending_enabled:
        return {'status':'blocked','phone':phone}
    now=datetime.now(timezone.utc)
    row=db.query(InterventionRequest).filter_by(instance_id=instance.id,code=code).first()
    if not row or row.notification_status not in {'sent','dispatching','unknown'}:
        return {'status':'unknown','phone':phone}
    if row.expires_at.tzinfo is None:
        row.expires_at=row.expires_at.replace(tzinfo=timezone.utc)
    if row.expires_at<=now or row.status=='expired':
        row.status='expired';db.commit()
        return {'status':'expired','phone':phone}
    if row.status=='claimed':
        if row.claimed_by_phone==phone:
            conversation=db.query(Conversation).filter_by(id=row.conversation_id,tenant_id=row.tenant_id).first()
            return {'status':'already_yours','phone':phone,'ticket':row,'context':context_for(db,conversation,row.reason) if conversation else 'Histórico indisponível.'}
        return {'status':'already_claimed','phone':phone}
    if row.status!='awaiting_claim':
        return {'status':'unavailable','phone':phone}
    # The tenant advisory lock serializes this claim across API workers.
    row.status='claimed';row.claimed_by_phone=phone;row.claimed_at=now
    db.commit()
    conversation=db.query(Conversation).filter_by(id=row.conversation_id,tenant_id=row.tenant_id).first()
    return {'status':'claimed','phone':phone,'ticket':row,'context':context_for(db,conversation,row.reason) if conversation else 'Histórico indisponível.'}


def send_claim_reply(instance, phone, result):
    messages={
        'unauthorized':'Este número não está autorizado a assumir atendimentos nesta empresa.',
        'unknown':'Não encontrei um atendimento aberto com esse código.',
        'expired':'Este código expirou. Peça à equipe um novo alerta.',
        'already_claimed':'Este atendimento já foi assumido por outra pessoa.',
        'unavailable':'Este atendimento não está disponível para aceite.',
        'blocked':'O envio do atendimento está pausado. Peça à administração para verificar a configuração.',
    }
    if result['status'] in {'claimed','already_yours'}:
        ticket=result['ticket']
        message=(f'Atendimento {ticket.code} atribuído a você.\n{result.get("context","")}'
                 if result['status']=='claimed' else f'Contexto do atendimento {ticket.code}:\n{result.get("context","")}')
    else:
        message=messages[result['status']]
    if result['status']=='blocked':
        return
    try:
        group_client(instance).send_text(phone,message[:4000])
        if result.get('ticket'):
            result['ticket'].context_delivery_status='sent'
    except (ZapiError,ValueError):
        if result.get('ticket'):
            result['ticket'].context_delivery_status='failed'
