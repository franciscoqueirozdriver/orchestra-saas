"""Structured conversation contract. The model proposes; the backend disposes."""
import json
import re

INTENTS = frozenset({'pedido', 'duvida', 'correcao', 'follow_up', 'mudanca_assunto',
                     'reclamacao', 'confirmacao', 'opt_out', 'humano', 'outro'})
SENTIMENTS = frozenset({'positivo', 'neutro', 'negativo', 'urgente'})
ACTIONS = frozenset({'respond', 'ask', 'handoff', 'wait'})
FACT_KEYS = frozenset({'interlocutor_name', 'preference', 'objection', 'city',
                       'address', 'preferred_date', 'preferred_time'})
VISIT_FIELDS = {
    'channel_confirmation': {'use_current', 'decline_current', 'unknown'},
    'receiver_confirmation': {'customer', 'other_person', 'unknown'},
    'next_required_field': {'city', 'address', 'preferred_date', 'preferred_time',
                            'receiver_confirmation', 'receiver_name',
                            'return_channel_confirmation', 'alternate_phone', 'none'},
}


def _strip_fence(raw):
    if raw.startswith('```'):
        return re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.I).strip()
    return raw


def parse_decision_envelope(value):
    raw = _strip_fence(str(value or '').strip())
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    reply = parsed.get('reply')
    if not isinstance(reply, str) or not reply.strip() or len(reply) > 24000:
        return None
    decision = parsed.get('decision')
    if not isinstance(decision, dict):
        return None
    intent, sentiment, action = decision.get('intent'), decision.get('sentiment'), decision.get('action')
    if not all(isinstance(item, str) for item in (intent, sentiment, action)):
        return None
    if intent not in INTENTS or sentiment not in SENTIMENTS or action not in ACTIONS:
        return None
    facts = {}
    raw_facts = decision.get('facts')
    if isinstance(raw_facts, dict):
        for key, item in raw_facts.items():
            if key in FACT_KEYS and isinstance(item, str) and 0 < len(item.strip()) <= 300:
                facts[key] = item.strip()
    raw_pending = decision.get('pending')
    if raw_pending is None:
        raw_pending = []
    elif not isinstance(raw_pending, list):
        return None
    pending = [item.strip()[:200] for item in raw_pending
               if isinstance(item, str) and item.strip()][:10]
    clean = {
        'intent': intent, 'sentiment': sentiment, 'action': action,
        'stage': str(decision.get('stage') or '')[:120],
        'next_best_action': str(decision.get('next_best_action') or '')[:120],
        'facts': facts, 'pending': pending,
    }
    envelope = {'reply': reply.strip(), 'decision': clean}
    if 'visit' in parsed:
        envelope['visit'] = parsed.get('visit')
    return envelope


def clean_visit(value):
    if not isinstance(value, dict):
        return None
    clean = {}
    for key, allowed in VISIT_FIELDS.items():
        item = value.get(key)
        if item is None:
            continue
        if not isinstance(item, str) or item not in allowed:
            return None
        clean[key] = item
    if len(clean) != len(VISIT_FIELDS):
        return None
    name = value.get('receiver_name')
    if isinstance(name, str) and 0 < len(name.strip()) <= 120 and not any(ch.isdigit() for ch in name):
        clean['receiver_name'] = name.strip()
    return clean


def state_patch(decision):
    decision = decision if isinstance(decision, dict) else {}
    return {
        'intent': decision.get('intent', 'outro'),
        'sentiment': decision.get('sentiment', 'neutro'),
        'stage': str(decision.get('stage') or '')[:120],
        'next_best_action': str(decision.get('next_best_action') or '')[:120],
        'pending': list(decision.get('pending') or [])[:10],
        'decision_action': decision.get('action', 'respond'),
    }


def contract_instructions(visit):
    base = ('Responda somente com um objeto JSON válido, sem markdown, no contrato conversation.v1: '
            '{"reply":"mensagem natural para o cliente","decision":{"intent":"pedido|duvida|correcao|follow_up|mudanca_assunto|reclamacao|confirmacao|opt_out|humano|outro",'
            '"sentiment":"positivo|neutro|negativo|urgente","stage":"rótulo curto",'
            '"action":"respond|ask|handoff|wait","facts":{"interlocutor_name":"","preference":"","objection":"","city":"","address":"","preferred_date":"","preferred_time":""},'
            '"pending":["dado ainda necessário"],"next_best_action":"rótulo curto"}}. '
            'A decisão descreve o que você entendeu; ela não autoriza preço, cancelamento, reserva ou confirmação. '
            'Use action=handoff somente se a pessoa pedir atendimento humano ou se não houver base segura para responder. '
            'Use action=wait apenas para confirmação isolada sem pergunta pendente. '
            'facts deve conter apenas dados explicitamente informados pela pessoa. Não invente.')
    if not visit:
        return base
    return (base + ' Inclua também o objeto "visit" quando houver interpretação comercial: '
            '{"visit":{"channel_confirmation":"use_current|decline_current|unknown",'
            '"receiver_confirmation":"customer|other_person|unknown",'
            '"receiver_name":null,"next_required_field":"city|address|preferred_date|preferred_time|receiver_confirmation|receiver_name|return_channel_confirmation|alternate_phone|none"}}. '
            'Use unknown quando não houver confirmação clara. Nunca declare visita confirmada.')
