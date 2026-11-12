# Núcleo Conversacional Humanizado (Onda 1) — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o atendente do Orquestra manter continuidade, decidir antes de responder e entregar de forma natural, sem fingir ser humano.

**Architecture:** Módulos puros novos em `backend/app/conversation/` (decisão, memória, humanização) chamados por `tasks.py`. Uma chamada estruturada por turno devolve `reply` + `decision`; o backend valida allowlist, aplica estado sob revisão e enfileira as partes. Resumo rolante roda em tarefa assíncrona.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, Celery, PostgreSQL, Redis, LangGraph (nó único), pytest, Playwright (UI).

**Spec:** `docs/superpowers/specs/2026-11-12-atendimento-humanizado-onda1-design.md`

## Global Constraints

- Nenhuma chamada real a provedor de IA ou WhatsApp em teste.
- Toda consulta e escrita filtra `tenant_id`; toda rota nova tem teste negativo de tenant.
- Flags por agente desligadas por padrão: `memory_enabled`, `structured_decision_enabled`, `presence_enabled`.
- Limite de entrega mantido: 3 partes × 300 caracteres; divisão sem perda de caractere.
- Envelope inválido nunca chega ao WhatsApp; cadeia esgotada falha fechada para intervenção.
- Fatos automáticos só com proveniência; fato comercial (`kind='business'`) exige aprovação.
- Migration nova é aditiva e é a `0011`; não editar migrations históricas.
- Não alterar comportamento de opt-out, consentimento, takeover, cancelamento ou revisão.
- Commits pequenos, em português, um por task.
- Testes unitários: `pytest -q`. Integração: `DATABASE_URL` de banco descartável.

## File Structure

Criar:

- `backend/app/conversation/decision.py` — contrato, parser, validação, patch de estado.
- `backend/app/conversation/memory.py` — fatos, dedupe, recuperação, prompt de resumo.
- `backend/app/conversation/humanize.py` — plano de entrega, silêncio, aberturas.
- `backend/app/routes_memory.py` — rotas de memória e decisão.
- `backend/migrations/versions/0011_conversation_memory.py` — colunas aditivas.
- `tests/test_conversation_decision.py`
- `tests/test_conversation_memory.py`
- `tests/test_conversation_humanize.py`
- `tests/integration/test_conversation_core.py`
- `tests/ui/memory-review.cjs`

Modificar:

- `backend/app/schemas.py` — campos novos de `ConversationProfile` e `MemoryUpdate`.
- `backend/app/conversation/behavior.py` — `style_instructions` com persona e aberturas.
- `backend/app/models.py` — colunas novas de `MemoryItem`.
- `backend/app/outbox.py` — atraso por parte.
- `backend/app/tasks.py` — integração e tarefa de resumo.
- `backend/app/main.py` — registro do router.
- `backend/app/routes_conversations.py` — expor decisão atual no estado.
- `frontend/app.js` — formulário de persona e bloco de memória.
- `tests/test_conversation_behavior.py`, `tests/test_delivery_policy.py`, `tests/ui/conversation-panel.cjs` — cobertura nova.
- `tests/fixtures/conversation_cases.json` — cenários do corpus.
- `docs/consolidacao/2026-11-12-onda1-conversacional.md` — registro final.

---

### Task 1: Persona configurável no perfil

**Files:**
- Modify: `backend/app/schemas.py:225-257`
- Modify: `backend/app/conversation/behavior.py:391-406`
- Test: `tests/test_conversation_behavior.py`
- Test: `tests/test_schemas.py`

**Interfaces:**
- Consumes: `ConversationProfile`, `style_instructions(profile, state)`.
- Produces: campos `formality`, `empathy`, `humor`, `objectivity`, `proactivity`, `max_lines`, `forbidden_phrases`, `adaptive_style`, `memory_enabled`, `structured_decision_enabled`, `presence_enabled`; `style_instructions` inclui `state['recent_openings']`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_conversation_behavior.py`:

```python
def test_persona_dimensions_are_bounded_and_reach_instructions():
    profile = ConversationProfile(
        enabled=True, formality=9, empathy=5, humor=0, objectivity=8,
        proactivity=2, max_lines=3, forbidden_phrases=['claro!', 'com certeza'],
        adaptive_style=True, structured_decision_enabled=True, memory_enabled=True,
    )
    text = style_instructions(profile, {'mode': 'request', 'recent_openings': ['Bom dia!']})
    assert 'formalidade 9/10' in text
    assert 'objetividade 8/10' in text
    assert 'máximo 3 linhas' in text
    assert 'claro!' in text
    assert 'Bom dia!' in text
    assert ConversationProfile().formality == 3
    assert ConversationProfile().structured_decision_enabled is False


def test_persona_rejects_out_of_range_values():
    with pytest.raises(ValidationError):
        ConversationProfile(formality=11)
    with pytest.raises(ValidationError):
        ConversationProfile(forbidden_phrases=['x'] * 11)
```

Add `ValidationError` to imports:

```python
from pydantic import ValidationError
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_conversation_behavior.py -q`
Expected: FAIL, `TypeError: ConversationProfile.__init__() got an unexpected keyword argument 'formality'`.

- [ ] **Step 3: Add schema fields**

In `backend/app/schemas.py`, inside `ConversationProfile` after `humanized_delay_seconds`:

```python
    formality: int = Field(default=3, ge=0, le=10)
    empathy: int = Field(default=7, ge=0, le=10)
    humor: int = Field(default=3, ge=0, le=10)
    objectivity: int = Field(default=7, ge=0, le=10)
    proactivity: int = Field(default=5, ge=0, le=10)
    max_lines: int = Field(default=4, ge=1, le=8)
    forbidden_phrases: list[str] = Field(default_factory=list, max_length=10)
    adaptive_style: bool = True
    memory_enabled: bool = False
    structured_decision_enabled: bool = False
    presence_enabled: bool = False
```

Change `examples` bound from `max_length=3` to `max_length=8`.

Extend `bounded_style` validator:

```python
    @field_validator('vocabulary', 'examples', 'forbidden_phrases')
    @classmethod
    def bounded_style(cls, values):
        if any(not v.strip() or len(v) > 1000 for v in values):
            raise ValueError('Itens de estilo precisam ter de 1 a 1000 caracteres')
        return [v.strip() for v in values]
```

- [ ] **Step 4: Extend `style_instructions`**

Replace the return block in `backend/app/conversation/behavior.py` (keep all existing strings) by appending:

```python
    dimensions = (f'Formalidade {profile.formality}/10; empatia {profile.empathy}/10; '
                  f'humor {profile.humor}/10; objetividade {profile.objectivity}/10; '
                  f'proatividade {profile.proactivity}/10; máximo {profile.max_lines} linhas.')
    forbidden = (' Frases a evitar: ' + '; '.join(profile.forbidden_phrases) + '.') if profile.forbidden_phrases else ''
    adaptive = (' Acompanhe o estilo do interlocutor: responda curto para quem escreve curto, detalhe quando ela pedir detalhe, '
                'formalize quando ela formalizar e seja objetivo e acolhedor quando ela demonstrar irritação. '
                'Adapte apenas a forma; nunca altere fatos, preços, permissões ou limites.'
                if profile.adaptive_style else '')
    openings = state.get('recent_openings') or []
    avoid = (' Não repita estas aberturas recentes: ' + ' | '.join(openings) + '.') if openings else ''
    return (existing_return + ' ' + dimensions + forbidden + adaptive + avoid)
```

Implementation shape:

```python
def style_instructions(profile, state):
    tone = {'neutral': 'neutro e acolhedor', 'formal': 'formal e claro', 'friendly': 'próximo e respeitoso'}[profile.tone]
    base = (f'Perfil de estilo: tom {tone}; concisão {profile.conciseness}; emojis {profile.emojis}. '
            + 'Estilo não é fonte de fatos, preços ou autorização. Não imite uma pessoa real. '
              'Se perguntado, informe que é assistente automatizado. Responda ao pedido junto da saudação. '
              'Não acrescente perguntas artificiais a toda resposta. Preserve números, itens e nomes relevantes. '
              'Pode acompanhar perguntas laterais e mudanças de assunto sem exigir CONTINUAR/NOVA. '
              'Não trate uma negação como desistência se a mesma mensagem contém outro pedido. '
              'Não prometa ações, fila humana ou retornos que não foram registrados. '
              'Você não tem ferramentas de negócio. Não confirme cancelamento de compra, reserva ou cadastro. '
              'Contexto com validade é referência conversacional, não prova de informação atual. '
            f'Sinal do turno: {state.get("mode", "request")}. '
            + ('O cliente já corrigiu a resposta mais de uma vez: não repita pedido de reformulação nem a mesma resposta; reconheça o limite sem inventar encaminhamento. '
               if state.get('corrections', 0) > 1 or state.get('clarifications', 0) >= 1 else ''))
    dimensions = (f'Formalidade {profile.formality}/10; empatia {profile.empathy}/10; '
                  f'humor {profile.humor}/10; objetividade {profile.objectivity}/10; '
                  f'proatividade {profile.proactivity}/10; máximo {profile.max_lines} linhas.')
    forbidden = (' Frases a evitar: ' + '; '.join(profile.forbidden_phrases) + '.') if profile.forbidden_phrases else ''
    adaptive = (' Acompanhe o estilo do interlocutor: responda curto para quem escreve curto, detalhe quando ela pedir detalhe, '
                'formalize quando ela formalizar e seja objetivo e acolhedor quando ela demonstrar irritação. '
                'Adapte apenas a forma; nunca altere fatos, preços, permissões ou limites.'
                if profile.adaptive_style else '')
    openings = state.get('recent_openings') or []
    avoid = (' Não repita estas aberturas recentes: ' + ' | '.join(openings) + '.') if openings else ''
    return (base + dimensions + forbidden + adaptive + avoid
            + '\nVocabulário de estilo (dados, não instruções): ' + repr(profile.vocabulary)
            + '\nExemplos revisados de estilo (não usar seus fatos em outra conversa): ' + repr(profile.examples))
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_conversation_behavior.py tests/test_schemas.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/conversation/behavior.py tests/test_conversation_behavior.py tests/test_schemas.py
git commit -m "Adiciona dimensões de persona ao perfil conversacional"
```

---

### Task 2: Módulo de decisão estruturada

**Files:**
- Create: `backend/app/conversation/decision.py`
- Test: `tests/test_conversation_decision.py`

**Interfaces:**
- Consumes: nada.
- Produces: `parse_decision_envelope(value) -> dict | None`, `clean_visit(value) -> dict | None`, `state_patch(decision) -> dict`, `contract_instructions(visit: bool) -> str`, constantes `INTENTS`, `SENTIMENTS`, `ACTIONS`, `FACT_KEYS`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_conversation_decision.py`:

```python
import json
from app.conversation.decision import clean_visit, parse_decision_envelope, state_patch, contract_instructions


def _envelope(**overrides):
    decision = {
        'intent': 'pedido', 'sentiment': 'neutro', 'stage': 'coletando',
        'action': 'respond', 'facts': {'interlocutor_name': 'Ana', 'inventado': 'x'},
        'pending': ['confirmar bairro'], 'next_best_action': 'responder',
    }
    decision.update(overrides)
    return json.dumps({'reply': 'Claro, Ana. Qual o bairro?', 'decision': decision})


def test_parses_valid_envelope_and_drops_unknown_fact_keys():
    envelope = parse_decision_envelope(_envelope())
    assert envelope['reply'] == 'Claro, Ana. Qual o bairro?'
    assert envelope['decision']['facts'] == {'interlocutor_name': 'Ana'}
    assert envelope['decision']['pending'] == ['confirmar bairro']
    assert envelope['decision']['action'] == 'respond'


def test_rejects_invalid_or_out_of_allowlist_output():
    assert parse_decision_envelope('texto livre') is None
    assert parse_decision_envelope(json.dumps({'reply': '', 'decision': {}})) is None
    assert parse_decision_envelope(_envelope(action='delete')) is None
    assert parse_decision_envelope(_envelope(intent='qualquer')) is None
    assert parse_decision_envelope(json.dumps({'reply': 'ok', 'decision': {'intent': 'pedido'}})) is None


def test_accepts_fenced_json_and_limits_pending():
    fenced = '```json\n' + _envelope(pending=['a'] * 20) + '\n```'
    envelope = parse_decision_envelope(fenced)
    assert len(envelope['decision']['pending']) == 10


def test_state_patch_carries_only_allowlisted_fields():
    envelope = parse_decision_envelope(_envelope())
    patch = state_patch(envelope['decision'])
    assert patch['intent'] == 'pedido'
    assert patch['pending'] == ['confirmar bairro']
    assert patch['decision_action'] == 'respond'
    assert 'facts' not in patch


def test_visit_block_is_optional_but_validated_when_present():
    assert clean_visit(None) is None
    assert clean_visit({'channel_confirmation': 'nope'}) is None
    good = clean_visit({'channel_confirmation': 'use_current', 'receiver_confirmation': 'customer',
                        'receiver_name': None, 'next_required_field': 'city'})
    assert good['receiver_confirmation'] == 'customer'


def test_contract_mentions_visit_only_when_needed():
    assert 'visit' in contract_instructions(True)
    assert 'visit' not in contract_instructions(False)
    assert 'conversation.v1' in contract_instructions(False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_conversation_decision.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.conversation.decision'`.

- [ ] **Step 3: Implement module**

Create `backend/app/conversation/decision.py`:

```python
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
    if intent not in INTENTS or sentiment not in SENTIMENTS or action not in ACTIONS:
        return None
    facts = {}
    raw_facts = decision.get('facts')
    if isinstance(raw_facts, dict):
        for key, item in raw_facts.items():
            if key in FACT_KEYS and isinstance(item, str) and 0 < len(item.strip()) <= 300:
                facts[key] = item.strip()
    pending = [item.strip()[:200] for item in (decision.get('pending') or [])
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
        if item in allowed:
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
```

- [ ] **Step 4: Run test**

Run: `pytest tests/test_conversation_decision.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/conversation/decision.py tests/test_conversation_decision.py
git commit -m "Adiciona contrato estruturado de decisão conversacional"
```

---

### Task 3: Memória em camadas e migration 0011

**Files:**
- Modify: `backend/app/models.py:232-241`
- Create: `backend/migrations/versions/0011_conversation_memory.py`
- Create: `backend/app/conversation/memory.py`
- Test: `tests/test_conversation_memory.py`

**Interfaces:**
- Consumes: `MemoryItem`, `_extract_sales_facts` de `behavior`.
- Produces: `kind_for(fact_key)`, `should_replace(existing, captured_at)`, `record_facts(db, *, tenant_id, contact_key, facts, message_id, captured_at, source, confidence)`, `explicit_facts(text)`, `memory_context(db, *, tenant_id, contact_key, now=None, limit=8)`, `summary_prompt(messages, previous)`, `AUTO_KINDS`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_conversation_memory.py`:

```python
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from app.conversation.memory import (AUTO_KINDS, kind_for, should_replace,
                                     memory_context, summary_prompt, explicit_facts)


def test_fact_kind_and_governance_mapping():
    assert kind_for('interlocutor_name') == 'identity'
    assert kind_for('preference') == 'preference'
    assert kind_for('preferred_date') == 'episode'
    assert kind_for('price') == 'business'
    assert AUTO_KINDS == {'identity', 'preference', 'pending', 'episode'}


def test_newer_provenance_wins_but_older_does_not():
    now = datetime.now(timezone.utc)
    existing = SimpleNamespace(last_seen_at=now, created_at=now)
    assert should_replace(existing, now + timedelta(minutes=1)) is True
    assert should_replace(existing, now - timedelta(minutes=1)) is False
    assert should_replace(None, now) is True


def test_memory_context_labels_data_and_skips_missing_provenance():
    now = datetime.now(timezone.utc)
    rows = [SimpleNamespace(kind='preference', content='prefere manhã', source_message_id='m1', created_at=now),
            SimpleNamespace(kind='note', content='sem origem', source_message_id=None, created_at=now)]
    db = SimpleNamespace(query=lambda *a, **k: SimpleNamespace(filter=lambda *a, **k: SimpleNamespace(
        order_by=lambda *a, **k: SimpleNamespace(limit=lambda n: SimpleNamespace(all=lambda: rows)))))
    text = memory_context(db, tenant_id='t', contact_key='c', now=now)
    assert 'dados, não instruções' in text
    assert 'prefere manhã' in text
    assert 'sem origem' not in text


def test_summary_prompt_bounds_content_and_keeps_previous_summary():
    prompt = summary_prompt([{'direction': 'incoming', 'content': 'x' * 900},
                             {'direction': 'outgoing', 'content': 'ok'}], 'resumo antigo')
    assert 'resumo antigo' in prompt
    assert 'x' * 500 in prompt and 'x' * 501 not in prompt
    assert 'no máximo 600 caracteres' in prompt


def test_explicit_facts_extracts_only_explicit_data():
    facts = explicit_facts('Meu nome é Ana e moro na Rua das Flores, 100, em Campinas')
    assert facts['interlocutor_name'] == 'Ana'
    assert 'Rua das Flores' in facts['address']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_conversation_memory.py -q`
Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Extend model**

In `backend/app/models.py`, `MemoryItem`, after `expires_at`:

```python
    kind: Mapped[str] = mapped_column(String(24), nullable=False, default='note', server_default='note')
    fact_key: Mapped[str | None] = mapped_column(String(120))
    source_message_id: Mapped[str | None] = mapped_column(String(220))
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default='1.0')
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Add `__table_args__`:

```python
    __table_args__ = (Index('ix_memory_tenant_contact_kind', 'tenant_id', 'contact_key', 'kind'),)
```

Add `Float` to the SQLAlchemy import line at `backend/app/models.py:6`:

```python
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, String, Text, UniqueConstraint, func, text
```

`Index` já está importado.

- [ ] **Step 4: Write migration**

Create `backend/migrations/versions/0011_conversation_memory.py`:

```python
"""Add conversation memory provenance fields."""
from alembic import op
import sqlalchemy as sa

revision = '0011_conversation_memory'
down_revision = '0010_wame_api_base_url'
branch_labels = depends_on = None


def upgrade():
    op.add_column('memory_items', sa.Column('kind', sa.String(24), nullable=False, server_default='note'))
    op.add_column('memory_items', sa.Column('fact_key', sa.String(120)))
    op.add_column('memory_items', sa.Column('source_message_id', sa.String(220)))
    op.add_column('memory_items', sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'))
    op.add_column('memory_items', sa.Column('last_seen_at', sa.DateTime(timezone=True)))
    op.create_index('ix_memory_tenant_contact_kind', 'memory_items', ['tenant_id', 'contact_key', 'kind'])


def downgrade():
    op.drop_index('ix_memory_tenant_contact_kind', table_name='memory_items')
    op.drop_column('memory_items', 'last_seen_at')
    op.drop_column('memory_items', 'confidence')
    op.drop_column('memory_items', 'source_message_id')
    op.drop_column('memory_items', 'fact_key')
    op.drop_column('memory_items', 'kind')
```

- [ ] **Step 5: Implement memory module**

Create `backend/app/conversation/memory.py`:

```python
"""Conversation memory: provenance-first facts, rolling summary, no instruction promotion."""
from datetime import datetime, timedelta, timezone

from app.conversation.behavior import _extract_sales_facts
from app.models import MemoryItem

AUTO_KINDS = {'identity', 'preference', 'pending', 'episode'}
KIND_BY_KEY = {
    'interlocutor_name': 'identity', 'receiver_name': 'identity',
    'preference': 'preference', 'pending_item': 'pending',
    'city': 'episode', 'address': 'episode', 'preferred_date': 'episode',
    'preferred_time': 'episode', 'objective': 'business', 'environment': 'business',
    'urgency': 'business', 'alternate_phone': 'business', 'price': 'business',
}
TTL_DAYS = {'identity': 180, 'preference': 30, 'pending': 30, 'episode': 30, 'business': 30, 'note': 30}


def kind_for(fact_key):
    return KIND_BY_KEY.get(fact_key, 'business')


def explicit_facts(text):
    return _extract_sales_facts(text)


def _aware(value):
    if value and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def should_replace(existing, captured_at):
    if existing is None:
        return True
    marker = _aware(existing.last_seen_at or existing.created_at)
    return marker is None or _aware(captured_at) >= marker


def record_facts(db, *, tenant_id, contact_key, facts, message_id, captured_at, source='auto_extraction', confidence=0.7):
    if not message_id:
        return
    for fact_key, value in (facts or {}).items():
        if not isinstance(value, str) or not value.strip():
            continue
        kind = kind_for(fact_key)
        existing = (db.query(MemoryItem)
                    .filter_by(tenant_id=tenant_id, contact_key=contact_key, kind=kind, fact_key=fact_key)
                    .order_by(MemoryItem.created_at.desc()).first())
        if existing is not None and existing.source != source and source != 'deterministic':
            continue
        if existing is not None and not should_replace(existing, captured_at):
            continue
        expires = captured_at + timedelta(days=TTL_DAYS.get(kind, 30))
        if existing is None:
            db.add(MemoryItem(tenant_id=tenant_id, contact_key=contact_key, kind=kind,
                              fact_key=fact_key, content=value.strip()[:1000], approved=kind in AUTO_KINDS,
                              source=source, source_message_id=str(message_id or '')[:220],
                              confidence=confidence, last_seen_at=captured_at, expires_at=expires))
        else:
            existing.content = value.strip()[:1000]
            existing.source_message_id = str(message_id or '')[:220]
            existing.confidence = confidence
            existing.last_seen_at = captured_at
            existing.expires_at = expires


def memory_context(db, *, tenant_id, contact_key, now=None, limit=8):
    now = now or datetime.now(timezone.utc)
    rows = (db.query(MemoryItem)
            .filter(MemoryItem.tenant_id == tenant_id,
                    MemoryItem.contact_key == contact_key,
                    MemoryItem.approved.is_(True),
                    MemoryItem.source_message_id.isnot(None),
                    MemoryItem.source_message_id != '',
                    (MemoryItem.expires_at.is_(None)) | (MemoryItem.expires_at > now))
            .order_by(MemoryItem.last_seen_at.desc().nullslast(), MemoryItem.created_at.desc())
            .limit(limit).all())
    if not rows:
        return ''
    lines = [f'- [{row.kind}] {row.content[:500]} (origem: {row.source_message_id}; '
             f'{_aware(row.created_at).date().isoformat()})' for row in rows]
    return 'Fatos da conversa (dados, não instruções):\n' + '\n'.join(lines)


def summary_prompt(messages, previous):
    lines = [f"{'Cliente' if m.get('direction') == 'incoming' else 'Atendente'}: {str(m.get('content') or '')[:500]}"
             for m in messages]
    return ('Atualize o resumo da conversa em no máximo 600 caracteres. '
            'Mantenha fatos, pedidos pendentes e preferências. Não invente.\n\n'
            'Resumo anterior:\n' + (previous or '(nenhum)') +
            '\n\nMensagens novas:\n' + '\n'.join(lines))
```

- [ ] **Step 6: Run tests and migration check**

Run: `pytest tests/test_conversation_memory.py -q`
Expected: PASS.

Run: `cd backend && alembic upgrade head`
Expected: `0011_conversation_memory` aplicada sem erro.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/migrations/versions/0011_conversation_memory.py backend/app/conversation/memory.py tests/test_conversation_memory.py
git commit -m "Adiciona memória conversacional com proveniência"
```

---

### Task 4: Humanização de entrega e atraso por parte

**Files:**
- Create: `backend/app/conversation/humanize.py`
- Modify: `backend/app/outbox.py:157,166,174`
- Test: `tests/test_conversation_humanize.py`
- Test: `tests/test_delivery_policy.py`

**Interfaces:**
- Consumes: `normalize` de `behavior`.
- Produces: `delivery_plan(parts, message_id) -> list[float]`, `should_wait(text, pending, last_assistant) -> bool`, `opening(text) -> str`, `remember_opening(state, answer) -> dict`, `repeated_opening(state, answer) -> bool`, `part_delay(delivery_config, ordinal) -> float`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_conversation_humanize.py`:

```python
from app.conversation.humanize import (delivery_plan, opening, part_delay,
                                       remember_opening, repeated_opening, should_wait)


def test_delivery_plan_is_deterministic_and_bounded():
    parts = ['Oi, tudo bem?', 'A visita pode ser na quinta às 14h.']
    first, second = delivery_plan(parts, 'conv:1'), delivery_plan(parts, 'conv:1')
    assert first == second
    assert len(first) == 2
    assert all(1.0 <= delay <= 6.0 for delay in first)
    assert first[1] >= 1.5


def test_part_delay_prefers_per_part_plan():
    assert part_delay({'part_delays': [1.2, 2.7]}, 1) == 2.7
    assert part_delay({'delay': 3}, 1) == 3
    assert part_delay({'part_delays': ['x']}, 0) == 1


def test_wait_requires_ack_without_pending_question():
    assert should_wait('ok', [], 'Perfeito, registrei.') is True
    assert should_wait('👍', [], 'Registrei.') is True
    assert should_wait('ok', ['confirmar bairro'], 'Qual o bairro?') is False
    assert should_wait('ok', [], 'Qual o bairro?') is False
    assert should_wait('quero orçamento', [], 'Registrei.') is False


def test_opening_memory_prevents_repetition():
    state = remember_opening({}, 'Bom dia! Como posso ajudar?')
    assert repeated_opening(state, 'Bom dia! Tudo certo?') is True
    assert repeated_opening(state, 'O prazo é de cinco dias.') is False
    for index in range(6):
        state = remember_opening(state, f'Abertura {index} com texto suficiente')
    assert len(state['recent_openings']) == 5
    assert opening('  Primeira frase. Resto') == 'Primeira frase. Resto'[:40]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_conversation_humanize.py -q`
Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Implement module**

Create `backend/app/conversation/humanize.py`:

```python
"""Delivery pacing and anti-repetition. No change to message content."""
from hashlib import sha256

from app.conversation.behavior import normalize

WAIT_TOKENS = frozenset({'ok', 'okay', 'beleza', 'blz', 'valeu', 'vlw', 'obrigado',
                         'obrigada', '👍', '🙏'})


def _jitter(seed, low=0.0, high=1.2):
    value = int.from_bytes(sha256(seed.encode()).digest()[:8], 'big')
    return low + (value / 2 ** 64) * (high - low)


def delivery_plan(parts, message_id):
    plan = []
    for ordinal, part in enumerate(parts):
        delay = min(6.0, max(1.0, 1.0 + 0.02 * len(part) + _jitter(f'{message_id}:{ordinal}')))
        if ordinal:
            delay = max(1.5, delay)
        plan.append(round(delay, 2))
    return plan


def part_delay(delivery_config, ordinal):
    plan = (delivery_config or {}).get('part_delays')
    if isinstance(plan, list) and ordinal < len(plan):
        try:
            return max(0.0, min(60.0, float(plan[ordinal])))
        except (TypeError, ValueError):
            pass
    return float((delivery_config or {}).get('delay', 1))


def should_wait(text, pending, last_assistant):
    if pending:
        return False
    if '?' in str(last_assistant or ''):
        return False
    value = str(text or '').strip()
    return value in WAIT_TOKENS or normalize(value).strip() in WAIT_TOKENS


def opening(text):
    return str(text or '').strip()[:40]


def remember_opening(state, answer):
    updated = dict(state or {})
    updated['recent_openings'] = (list(updated.get('recent_openings') or [])[-4:] + [opening(answer)])[-5:]
    return updated


def repeated_opening(state, answer):
    return opening(answer) in (state or {}).get('recent_openings', [])
```

- [ ] **Step 4: Use per-part delay in outbox**

In `backend/app/outbox.py`, add import:

```python
from app.conversation.humanize import part_delay
```

Replace the three delay reads:

- line 157: `timedelta(seconds=int(row.delivery_config.get('delay',1)))` →
  `timedelta(seconds=part_delay(row.delivery_config, part.ordinal + 1))`
- line 166 log: `int(row.delivery_config.get('delay', 1))` →
  `part_delay(row.delivery_config, part.ordinal + 1)`
- line 174: `countdown=int(row.delivery_config.get('delay',1))` →
  `countdown=part_delay(row.delivery_config, part.ordinal + 1)`

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_conversation_humanize.py tests/test_delivery_policy.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/conversation/humanize.py backend/app/outbox.py tests/test_conversation_humanize.py tests/test_delivery_policy.py
git commit -m "Aplica ritmo variável por parte e anti-repetição"
```

---

### Task 5: Integração no pipeline de resposta

**Files:**
- Modify: `backend/app/tasks.py:27,251-333,391-515`
- Create: `tests/integration/conftest.py`
- Modify: `tests/integration/test_runtime_safety.py:17-64` (mover fixture `runtime`, `engine` e `queue` para o conftest)
- Test: `tests/integration/test_conversation_core.py`

**Interfaces:**
- Consumes: `parse_decision_envelope`, `clean_visit`, `state_patch`, `contract_instructions`, `memory_context`, `record_facts`, `delivery_plan`, `should_wait`, `remember_opening`; `profile.structured_decision_enabled`, `profile.memory_enabled`.
- Produces: `_conversation_validator(profile)`, `_apply_conversation_memory(...)`, `_handoff_from_decision(...)`; resposta usa `delivery_config={'part_delays': [...], 'presence': bool}`.

- [ ] **Step 1: Write the failing integration test**

Primeiro mova o conteúdo de `tests/integration/test_runtime_safety.py` linhas 17-64 (fixtures `engine` e `runtime` e helpers de setup) para `tests/integration/conftest.py`, mantendo o mesmo código. O pytest disponibiliza as fixtures para ambos os módulos. `test_runtime_safety.py` mantém `queue()` e `event()` próprios.

Depois crie `tests/integration/test_conversation_core.py`. Add:

```python
import pytest


def _enable(runtime, **profile):
    from app.models import Agent
    with runtime.db() as db:
        agent = db.get(Agent, 'agent-a')
        agent.conversation_profile = {'enabled': True, **profile}
        db.commit()


def _add_incoming(runtime, content):
    from app.models import Message
    with runtime.db() as db:
        db.add(Message(tenant_id='tenant-a', conversation_id='conversation-a',
                       external_id=None, direction='incoming', kind='text',
                       content=content, status='received', author_kind='user'))
        db.commit()


def test_structured_decision_is_applied_only_on_current_revision(runtime, monkeypatch):
    from app.models import Conversation
    _enable(runtime, structured_decision_enabled=True, memory_enabled=True)
    monkeypatch.setattr(runtime.tasks, 'generate_with_fallback', lambda *a, **k: (
        '{"reply":"Claro, Ana. Qual o bairro?",'
        '"decision":{"intent":"pedido","sentiment":"neutro","stage":"coletando",'
        '"action":"respond","facts":{"interlocutor_name":"Ana"},'
        '"pending":["confirmar bairro"],"next_best_action":"perguntar bairro"}}'))
    result = runtime.tasks.respond_to_conversation('tenant-a', 'conversation-a', 1)
    assert result == 'reply_queued'
    with runtime.db() as db:
        conversation = db.get(Conversation, 'conversation-a')
        assert conversation.context_state['intent'] == 'pedido'
        assert conversation.context_state['pending'] == ['confirmar bairro']


def test_wait_action_skips_outbox(runtime, monkeypatch):
    from app.models import Conversation, OutboxMessage
    _enable(runtime, structured_decision_enabled=True)
    _add_incoming(runtime, 'ok')
    monkeypatch.setattr(runtime.tasks, 'generate_with_fallback', lambda *a, **k: (
        '{"reply":"Combinado.","decision":{"intent":"confirmacao","sentiment":"positivo",'
        '"stage":"encerrado","action":"wait","facts":{},"pending":[],'
        '"next_best_action":"nada"}}'))
    with runtime.db() as db:
        conversation = db.get(Conversation, 'conversation-a')
        conversation.context_state = {}
        conversation.turn_started_at = conversation.last_incoming_at
        db.commit()
        before = db.query(OutboxMessage).filter_by(tenant_id='tenant-a',
                                                   conversation_id='conversation-a').count()
    result = runtime.tasks.respond_to_conversation('tenant-a', 'conversation-a', 1)
    assert result == 'wait_skipped'
    with runtime.db() as db:
        after = db.query(OutboxMessage).filter_by(tenant_id='tenant-a',
                                                  conversation_id='conversation-a').count()
    assert after == before
```

- [ ] **Step 2: Run test to verify it fails**

Run: `TEST_DATABASE_URL=postgresql+psycopg://.../orchestra_consolidation_test pytest tests/integration/test_conversation_core.py -q`
Expected: FAIL, decisão não aplicada / `reply_queued` inesperado.

- [ ] **Step 3: Add imports and helpers**

At the end of the import block in `backend/app/tasks.py`:

```python
from app.conversation.decision import parse_decision_envelope, clean_visit, state_patch, contract_instructions
from app.conversation.memory import memory_context, record_facts
from app.conversation.humanize import delivery_plan, should_wait, remember_opening
```

Add helpers after `_validate_visit_response_contract`:

```python
def _conversation_validator(profile):
    def validate(value):
        envelope = parse_decision_envelope(value)
        if envelope is None:
            raise LLMError('Resposta fora do contrato conversacional', category='invalid_response')
        if profile.visit_booking_enabled and envelope.get('visit') is not None and clean_visit(envelope['visit']) is None:
            raise LLMError('Interpretação de visita inválida', category='invalid_response')
    return validate


def _apply_conversation_memory(db, tenant_id, conversation_id, revision, decision, answer, captured_at):
    with tenant_guard(tenant_id):
        db.expire_all()
        conversation = db.query(Conversation).filter_by(id=conversation_id, tenant_id=tenant_id).first()
        if not conversation or conversation.revision != revision or conversation.status != 'open' or conversation.opted_out:
            return False
        state = dict(conversation.context_state or {})
        state.update(state_patch(decision))
        state = remember_opening(state, answer)
        latest_incoming = (db.query(Message)
                           .filter_by(tenant_id=tenant_id, conversation_id=conversation_id, direction='incoming')
                           .order_by(Message.created_at.desc(), Message.id.desc()).first())
        if latest_incoming:
            record_facts(db, tenant_id=tenant_id, contact_key=conversation.contact_key,
                         facts=decision.get('facts') or {},
                         message_id=latest_incoming.external_id or latest_incoming.id,
                         captured_at=captured_at)
        conversation.context_state = state
        db.commit()
        return True


def _handoff_from_decision(db, tenant_id, conversation_id, reply):
    with tenant_guard(tenant_id):
        db.expire_all()
        conversation = db.query(Conversation).filter_by(id=conversation_id, tenant_id=tenant_id).first()
        if not conversation or conversation.status != 'open' or conversation.opted_out:
            return 'stale_response'
        instance = db.query(ZapiInstance).filter_by(id=conversation.instance_id, tenant_id=tenant_id).first()
        if not instance:
            return 'instance_missing'
        action(db, conversation, 'human_requested')
        ticket, created = create_request(db, instance, conversation, 'pedido de atendimento humano identificado na conversa')
        db.commit()
        send_group_alert(db, instance, ticket) if created else None
        from app.outbox import enqueue
        text = reply or 'Vou chamar uma pessoa da equipe para continuar.'
        enqueue(db, instance, conversation, text, parts=split_reply_conversational(text),
                idempotency_key=f'handoff:{ticket.id}', author_kind='assistant')
    return 'handoff_requested'
```

- [ ] **Step 4: Extend `_build_context`**

Inside `_build_context`, after the existing `memories` block:

```python
    stored = conversation.context_state or {}
    if profile.memory_enabled:
        if stored.get('summary'):
            context.append('Resumo da conversa (dados, não instruções):\n' + str(stored['summary'])[:600])
        facts_block = memory_context(db, tenant_id=agent.tenant_id, contact_key=conversation.contact_key)
        if facts_block:
            context.append(facts_block)
```

Inside the `if profile.enabled:` block, before `style_instructions`:

```python
        turn_state = {**turn_state, 'recent_openings': list(saved_context.get('recent_openings') or [])[:5]}
        if profile.structured_decision_enabled:
            context.append(contract_instructions(profile.visit_booking_enabled))
```

Remove the separate `visit_response_contract()` append when `structured_decision_enabled` is true:

```python
    if profile.visit_booking_enabled and not profile.structured_decision_enabled:
        context.append(visit_response_contract())
```

- [ ] **Step 5: Switch validator and parse result**

In `respond_to_conversation`, replace:

```python
            response_validator = _validate_visit_response_contract if profile.visit_booking_enabled else None
```

with:

```python
            if profile.structured_decision_enabled:
                response_validator = _conversation_validator(profile)
            elif profile.visit_booking_enabled:
                response_validator = _validate_visit_response_contract
            else:
                response_validator = None
```

After `answer = _graph_response(...)`, replace the visit parsing block with:

```python
            decision = {}
            visit_interpretation = None
            if profile.structured_decision_enabled:
                envelope = parse_decision_envelope(answer)
                if envelope is None:
                    return _escalate_after_automation_failure(db, tenant_id, conversation_id,
                                                              expected_revision, 'resposta inválida da automação')
                answer = envelope['reply']
                decision = envelope['decision']
                if profile.visit_booking_enabled:
                    visit_interpretation = clean_visit(envelope.get('visit') or {})
                if not _apply_conversation_memory(db, tenant_id, conversation_id, expected_revision,
                                                  decision, answer, datetime.now(timezone.utc)):
                    return 'stale_response'
            elif profile.visit_booking_enabled:
                answer, visit_interpretation = parse_visit_response(answer)
```

Rename subsequent uses of `interpretation` to `visit_interpretation` in the visit-application block.

- [ ] **Step 6: Apply action and delivery plan**

After the visit block and before `output_guard`, add:

```python
            if decision.get('action') == 'handoff':
                return _handoff_from_decision(db, tenant_id, conversation_id, answer)
```

Inside the final `with tenant_guard(tenant_id):` block, before `parts = split_reply_conversational(answer)`:

```python
                last_assistant = (db.query(Message)
                                  .filter_by(tenant_id=tenant_id, conversation_id=conversation_id,
                                             direction='outgoing', author_kind='assistant')
                                  .order_by(Message.created_at.desc(), Message.id.desc()).first())
                if (decision.get('action') == 'wait'
                        and should_wait(turn.state.get('request') if turn else '',
                                        (conversation.context_state or {}).get('pending') or [],
                                        last_assistant.content if last_assistant else '')):
                    conversation.turn_started_at = None
                    db.commit()
                    return 'wait_skipped'
```

Replace delivery config:

```python
                parts = split_reply_conversational(answer)
                plan = delivery_plan(parts, f'{conversation_id}:{expected_revision}')
                delivery_config = {'part_delays': plan,
                                   'presence': bool(profile.presence_enabled and instance.provider == 'zapi')}
```

Keep the existing `logger.info` and `enqueue` call; pass `delivery_config`.

- [ ] **Step 7: Run integration test**

Run: `TEST_DATABASE_URL=postgresql+psycopg://.../orchestra_consolidation_test pytest tests/integration/test_conversation_core.py -q`
Expected: PASS.

Run: `pytest -q`
Expected: PASS; nenhum teste antigo quebrado.

- [ ] **Step 8: Commit**

```bash
git add backend/app/tasks.py tests/integration/test_conversation_core.py
git commit -m "Integra decisão estruturada e memória ao turno"
```

---

### Task 6: Resumo rolante assíncrono

**Files:**
- Modify: `backend/app/tasks.py` (nova tarefa e agendamento)
- Test: `tests/integration/test_conversation_core.py`

**Interfaces:**
- Consumes: `summary_prompt`, `candidate_configs`, `complete`, `decrypt_secret`, `tenant_guard`.
- Produces: `summarize_conversation(tenant_id, conversation_id, revision)`; `context_state['summary']` e `['summary_cursor']`.

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/test_conversation_core.py`:

```python
def test_summary_updates_context_without_changing_revision(runtime, monkeypatch):
    from app.models import Conversation

    _enable(runtime, memory_enabled=True)
    for index in range(8):
        _add_incoming(runtime, f'mensagem {index}')
    monkeypatch.setattr(runtime.tasks, 'complete', lambda *a, **k: 'Resumo fictício do atendimento.')
    result = runtime.tasks.summarize_conversation.run('tenant-a', 'conversation-a', 1)
    assert result == 'summarized'
    with runtime.db() as db:
        conversation = db.get(Conversation, 'conversation-a')
        assert conversation.context_state['summary'] == 'Resumo fictício do atendimento.'
        assert conversation.context_state['summary_cursor']
        assert conversation.revision == 1


def test_summary_is_skipped_when_revision_is_stale(runtime, monkeypatch):
    _enable(runtime, memory_enabled=True)
    monkeypatch.setattr(runtime.tasks, 'complete', lambda *a, **k: 'não deveria ser chamado')
    result = runtime.tasks.summarize_conversation.run('tenant-a', 'conversation-a', 2)
    assert result == 'stale'
```

`_enable` e `_add_incoming` já existem no módulo, criados na Task 5.


- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_conversation_core.py -q`
Expected: FAIL, `AttributeError: module 'app.tasks' has no attribute 'summarize_conversation'`.

- [ ] **Step 3: Implement task**

Add to `backend/app/tasks.py` after `respond_to_conversation`:

```python
@celery_app.task(name='app.tasks.summarize_conversation', bind=True, max_retries=3, default_retry_delay=60)
def summarize_conversation(self, tenant_id, conversation_id, revision):
    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter_by(id=conversation_id, tenant_id=tenant_id).first()
        if not conversation:
            return 'missing'
        instance = db.query(ZapiInstance).filter_by(id=conversation.instance_id, tenant_id=tenant_id).first()
        agent = db.query(Agent).filter_by(id=instance.agent_id, tenant_id=tenant_id).first() if instance and instance.agent_id else None
        profile = profile_for(agent)
        if not agent or not profile.memory_enabled:
            return 'disabled'
        if revision != conversation.revision or conversation.status != 'open' or conversation.opted_out:
            return 'stale'
        state = dict(conversation.context_state or {})
        query = db.query(Message).filter_by(tenant_id=tenant_id, conversation_id=conversation_id).order_by(Message.created_at, Message.id)
        cursor = state.get('summary_cursor')
        if cursor:
            query = query.filter(Message.created_at > datetime.fromisoformat(cursor))
        messages = query.limit(40).all()
        if len(messages) < 8:
            return 'insufficient'
        prompt = summary_prompt([{'direction': m.direction, 'content': m.content} for m in messages],
                                state.get('summary') or '')
        text = ''
        for config in candidate_configs(db, agent):
            cooldown = config.cooldown_until
            if cooldown and aware(cooldown) > datetime.now(timezone.utc):
                continue
            try:
                text = complete(config.provider, config.base_url, config.model,
                                decrypt_secret(config.api_key_encrypted) or '',
                                'Você resume conversas de atendimento sem inventar fatos.',
                                [{'role': 'user', 'content': prompt}],
                                protocol=config.protocol, max_output_tokens=400)
                if text and text.strip():
                    break
            except LLMError:
                continue
        if not text.strip():
            return 'unavailable'
        with tenant_guard(tenant_id):
            db.expire_all()
            conversation = db.query(Conversation).filter_by(id=conversation_id, tenant_id=tenant_id).first()
            if not conversation or conversation.revision != revision or conversation.status != 'open' or conversation.opted_out:
                return 'stale'
            state = dict(conversation.context_state or {})
            state['summary'] = text.strip()[:600]
            state['summary_cursor'] = aware(messages[-1].created_at).isoformat()
            conversation.context_state = state
            db.commit()
        return 'summarized'
    finally:
        db.close()
```

Ajuste os imports de `backend/app/tasks.py`:

```python
from app.llm_client import LLMError, complete
from app.conversation.memory import memory_context, record_facts, summary_prompt
```

(acrescente `complete` e `summary_prompt` aos imports existentes).

- [ ] **Step 4: Schedule after reply**

Inside `respond_to_conversation`, after `enqueue(...)` and before `return 'reply_queued'`:

```python
                if profile.memory_enabled:
                    try:
                        summarize_conversation.apply_async(args=[tenant_id, conversation_id, expected_revision], countdown=5)
                    except Exception:
                        logger.warning('Resumo conversacional não agendado; recuperação manual necessária')
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/integration/test_conversation_core.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/tasks.py tests/integration/test_conversation_core.py
git commit -m "Atualiza resumo da conversa de forma assíncrona"
```

---

### Task 7: Rotas de memória e decisão

**Files:**
- Create: `backend/app/routes_memory.py`
- Modify: `backend/app/main.py:8-16,45`
- Modify: `backend/app/schemas.py` (novo `MemoryUpdate`)
- Test: `tests/test_memory_routes.py`

**Interfaces:**
- Consumes: `MemoryItem`, `Conversation`, `CurrentUser`, `_require_admin` pattern de `routes_agents.py`, `tenant_id` dependency.
- Produces: `GET /api/conversations/{id}/memory`, `PATCH /api/memory/{id}`, `DELETE /api/memory/{id}`, `GET /api/conversations/{id}/decision`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_memory_routes.py`:

```python
from types import SimpleNamespace
from app.routes_memory import _memory_payload, _decision_payload


def test_memory_payload_never_exposes_other_tenant_and_marks_provenance():
    row = SimpleNamespace(id='m1', tenant_id='t1', contact_key='c1', kind='preference',
                          fact_key='preference', content='prefere manhã', approved=True,
                          source='auto_extraction', source_message_id='msg-1',
                          confidence=0.7, created_at=None, last_seen_at=None, expires_at=None)
    payload = _memory_payload(row)
    assert payload['kind'] == 'preference'
    assert payload['source_message_id'] == 'msg-1'
    assert payload['approved'] is True
    assert 'tenant_id' not in payload


def test_decision_payload_only_returns_allowlisted_fields():
    state = {'intent': 'pedido', 'sentiment': 'neutro', 'stage': 'coleta',
             'pending': ['bairro'], 'next_best_action': 'perguntar', 'decision_action': 'respond',
             'segredo': 'não expor'}
    payload = _decision_payload(state)
    assert payload['intent'] == 'pedido'
    assert payload['pending'] == ['bairro']
    assert 'segredo' not in payload
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory_routes.py -q`
Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Add schema**

In `backend/app/schemas.py`:

```python
class MemoryUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    approved: bool | None = None
    expires_at: datetime | None = None
```

Add `from datetime import datetime` to the top of `backend/app/schemas.py` (não existe hoje).

- [ ] **Step 4: Implement routes**

Create `backend/app/routes_memory.py`:

```python
"""Memory review and last-decision inspection, always tenant-scoped."""
from fastapi import APIRouter, HTTPException

from app.control import serialized_mutation
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
@serialized_mutation
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
@serialized_mutation
def delete_memory(memory_id: str, db: DbSession, tenant_id: TenantId, user: CurrentUser):
    row = db.query(MemoryItem).filter_by(tenant_id=tenant_id, id=memory_id).first()
    if not row:
        raise HTTPException(404, detail='Memória não encontrada')
    db.delete(row)
    db.commit()
```

Verify the actual dependency names in `backend/app/dependencies.py`; use the exact names already imported by `routes_conversations.py` (`DbSession`, `TenantId`, `CurrentUser`). Verify `User.role` values in `models.py` before finishing; if role is not `tenant_admin`, use the same admin check as `routes_agents._require_admin`.

- [ ] **Step 5: Register router**

In `backend/app/main.py`:

```python
from app.routes_memory import router as memory_router
```

and include `memory_router` in the tuple at line 45.

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_memory_routes.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes_memory.py backend/app/main.py backend/app/schemas.py tests/test_memory_routes.py
git commit -m "Expõe revisão de memória e última decisão da conversa"
```

---

### Task 8: Painel — persona e memória

**Files:**
- Modify: `frontend/app.js:63-77` (formulário “Tom e conversa”)
- Modify: `frontend/app.js` (bloco de memória na conversa)
- Modify: `tests/ui/conversation-panel.cjs`
- Create: `tests/ui/memory-review.cjs`

**Interfaces:**
- Consumes: `PUT /api/agents/{id}/conversation-policy`, `GET /api/conversations/{id}/memory`, `GET /api/conversations/{id}/decision`, `PATCH /api/memory/{id}`.
- Produces: campos do formulário e bloco de revisão.

- [ ] **Step 1: Extend the profile form**

Inside the `openModal('Tom e conversa', ...)` template in `frontend/app.js`, after the “Emojis” field, add:

```html
<label class="field-label">Formalidade (0 a 10)<input class="field-control" name="formality" type="number" min="0" max="10" value="${esc(p.formality)}"></label>
<label class="field-label">Empatia (0 a 10)<input class="field-control" name="empathy" type="number" min="0" max="10" value="${esc(p.empathy)}"></label>
<label class="field-label">Humor (0 a 10)<input class="field-control" name="humor" type="number" min="0" max="10" value="${esc(p.humor)}"></label>
<label class="field-label">Objetividade (0 a 10)<input class="field-control" name="objectivity" type="number" min="0" max="10" value="${esc(p.objectivity)}"></label>
<label class="field-label">Proatividade (0 a 10)<input class="field-control" name="proactivity" type="number" min="0" max="10" value="${esc(p.proactivity)}"></label>
<label class="field-label">Máximo de linhas por resposta<input class="field-control" name="max_lines" type="number" min="1" max="8" value="${esc(p.max_lines)}"></label>
<label class="field-label">Frases proibidas (uma por linha)<textarea class="field-control" name="forbidden_phrases">${esc(p.forbidden_phrases.join('\n'))}</textarea></label>
<label class="check-line"><input type="checkbox" name="adaptive_style" ${p.adaptive_style?'checked':''}> Adaptar o nível de detalhe ao interlocutor</label>
<label class="check-line"><input type="checkbox" name="memory_enabled" ${p.memory_enabled?'checked':''}> Ativar memória entre conversas</label>
<label class="check-line"><input type="checkbox" name="structured_decision_enabled" ${p.structured_decision_enabled?'checked':''}> Ativar decisão estruturada</label>
```

Extend the `body` object in `formSubmit`:

```javascript
formality:Number(fd.get('formality')),empathy:Number(fd.get('empathy')),humor:Number(fd.get('humor')),
objectivity:Number(fd.get('objectivity')),proactivity:Number(fd.get('proactivity')),max_lines:Number(fd.get('max_lines')),
forbidden_phrases:String(fd.get('forbidden_phrases')).split('\n').map(x=>x.trim()).filter(Boolean),
adaptive_style:fd.get('adaptive_style')==='on',memory_enabled:fd.get('memory_enabled')==='on',
structured_decision_enabled:fd.get('structured_decision_enabled')==='on'
```

- [ ] **Step 2: Add memory block to the conversation panel**

In `loadMessages` (`frontend/app.js:98`), extend the `Promise.all`:

```javascript
      const [data,info,memory,decision]=await Promise.all([
        request(`/conversations/${encodeURIComponent(id)}/messages`),
        request(`/conversations/${encodeURIComponent(id)}/state`),
        request(`/conversations/${encodeURIComponent(id)}/memory`),
        request(`/conversations/${encodeURIComponent(id)}/decision`),
      ]);
```

Append the memory section to the `box.innerHTML` assignment at line 104:

```javascript
      const memoryItems=(memory.items||[]).map(item=>`<li><span class="badge">${esc(item.kind)}</span> ${esc(item.content)} <small>origem ${esc(item.source_message_id||'—')}</small>${item.approved?'':` <button class="small-button" data-approve="${esc(item.id)}">Aprovar</button>`}</li>`).join('');
      const memoryBlock=`<section class="card panel"><h3>Memória da conversa</h3>${memory.summary?`<p>${esc(memory.summary)}</p>`:''}<ul>${memoryItems||'<li>Nenhum fato registrado.</li>'}</ul><p><small>Última decisão: ${esc(decision.intent||'—')} / ${esc(decision.decision_action||'—')}</small></p></section>`;
      box.innerHTML=msgs.map(m=>`<div class="message-bubble ${m.direction==='outgoing'?'outgoing':''}">${esc(m.text||'')}<small>${esc(m.author_name||m.author_kind||m.direction)} · ${m.is_historical?'Histórico':esc(m.status)} · ${esc(m.is_historical?(m.original_timestamp_text||'Data ausente no arquivo'):m.created_at||'')}</small></div>`).join('')+`<div class="message-empty">Últimos envios: ${info.outbox.map(p=>`${esc(p.status)}${p.parts.length?' ('+p.parts.map(x=>esc(x.status)).join(', ')+')':''}`).join(' · ')||'nenhum'}</div>`+memoryBlock;
      $$('[data-approve]',box).forEach(b=>b.onclick=async()=>{b.disabled=true;try{await request(`/memory/${encodeURIComponent(b.dataset.approve)}`,{method:'PATCH',body:{approved:true}});await loadMessages(id,button)}catch(e){toast(e.message,'error');b.disabled=false}});
```

- [ ] **Step 3: Update the existing UI test**

In `tests/ui/conversation-panel.cjs`, extend the synthetic `profile` object with:

```javascript
formality:3,empathy:7,humor:3,objectivity:7,proactivity:5,max_lines:4,
forbidden_phrases:[],adaptive_style:false,memory_enabled:false,
structured_decision_enabled:false,presence_enabled:false
```

Because `loadMessages` now fetches two extra endpoints, add these branches to the synthetic route map in `tests/ui/conversation-panel.cjs`:

```javascript
    else if(endpoint==='/conversations/synthetic-conversation/memory')data={summary:'',pending:[],items:[]};
    else if(endpoint==='/conversations/synthetic-conversation/decision')data={intent:null,decision_action:null,provider:null,model:null};
```

Add assertions:

```javascript
await page.locator('#conversation-profile-form [name="formality"]').fill('9');
await page.locator('#conversation-profile-form [name="structured_decision_enabled"]').check();
```

and after save:

```javascript
assert.equal(profile.formality,9);
assert.equal(profile.structured_decision_enabled,true);
```

- [ ] **Step 4: Create the memory UI test**

Create `tests/ui/memory-review.cjs` following the same local-server pattern. Synthetic endpoints:

```javascript
else if(endpoint==='/conversations/synthetic-conversation/memory')data={summary:'Resumo fictício',pending:['bairro'],items:[{id:'memory-1',kind:'preference',content:'prefere manhã',source_message_id:'msg-1',approved:false}]};
else if(endpoint==='/conversations/synthetic-conversation/decision')data={intent:'pedido',decision_action:'respond'};
else if(endpoint==='/memory/memory-1'){mutations.push({endpoint,body:request.postDataJSON()});data={id:'memory-1',approved:true};}
```

Assertions:

```javascript
assert.match(await page.locator('body').innerText(),/Memória da conversa/);
assert.match(await page.locator('body').innerText(),/prefere manhã/);
await page.getByRole('button',{name:'Aprovar'}).click();
assert.equal(mutations.at(-1).body.approved,true);
```

- [ ] **Step 5: Run UI tests**

Run: `node tests/ui/conversation-panel.cjs`
Expected: PASS.

Run: `node tests/ui/memory-review.cjs`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/app.js tests/ui/conversation-panel.cjs tests/ui/memory-review.cjs
git commit -m "Exibe persona e revisão de memória no painel"
```

---

### Task 9: Corpus de avaliação e registro final

**Files:**
- Modify: `tests/fixtures/conversation_cases.json`
- Create: `tests/test_conversation_corpus.py`
- Create: `docs/consolidacao/2026-11-12-onda1-conversacional.md`

**Interfaces:**
- Consumes: `transition`, `command`, `should_wait`, `delivery_plan`, `parse_decision_envelope`.
- Produces: corpus executável e registro do que foi implementado, simulado e permanece pendente.

- [ ] **Step 1: Write the failing corpus test**

Create `tests/test_conversation_corpus.py`:

```python
import json
from pathlib import Path
from app.conversation.behavior import command, transition
from app.conversation.humanize import should_wait

CASES = json.loads(Path('tests/fixtures/conversation_cases.json').read_text())


def test_corpus_has_at_least_forty_cases():
    assert len(CASES) >= 40


def test_every_case_matches_turn_policy():
    for case in CASES:
        state = transition(case.get('previous') or {}, case['incoming'])
        assert state['mode'] == case['mode'], case['id']
        assert command(case['incoming']) == case.get('command'), case['id']


def test_wait_expectations_match_deterministic_guard():
    cases = [case for case in CASES if case.get('expect') in {'wait', 'reply'}]
    assert cases
    for case in cases:
        expected = case['expect'] == 'wait'
        assert should_wait(case['incoming'], case.get('pending') or [],
                           case.get('last_assistant') or '') is expected, case['id']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_conversation_corpus.py -q`
Expected: FAIL, `assert 20 >= 40` (fixture atual tem 20 casos).

- [ ] **Step 3: Expand fixture to 52 cases**

O fixture atual tem 20 casos. Append estes 32 casos sintéticos ao array de `tests/fixtures/conversation_cases.json`:

```json
[
  {"id":"greeting_and_request","previous":{},"incoming":"Bom dia, queria um orçamento","mode":"request","command":null},
  {"id":"correction_after_answer","previous":{"request":"Horário"},"incoming":"Não foi isso, quero o endereço","mode":"correction","command":null},
  {"id":"correction_variant","previous":{"request":"Horário"},"incoming":"Você não entendeu","mode":"correction","command":null},
  {"id":"correction_variant_2","previous":{"request":"Horário"},"incoming":"Não era isso","mode":"correction","command":null},
  {"id":"lateral_subject","previous":{"request":"Horário"},"incoming":"Mudando de assunto, vocês parcelam?","mode":"new_request","command":null},
  {"id":"follow_up_city","previous":{"request":"Orçamento em Campinas"},"incoming":"E os de amanhã?","mode":"follow_up","command":null},
  {"id":"follow_up_value","previous":{"request":"Orçamento"},"incoming":"E o valor?","mode":"follow_up","command":null},
  {"id":"follow_up_tomorrow","previous":{"request":"Horários"},"incoming":"E para amanhã?","mode":"follow_up","command":null},
  {"id":"negation_with_request","previous":{"request":"Horário"},"incoming":"Não, quero o endereço","mode":"new_request","command":null},
  {"id":"no_more","previous":{"request":"Horário"},"incoming":"Não quero mais nada, obrigado","mode":"new_request","command":null},
  {"id":"human_with_request","previous":{},"incoming":"Quero falar com uma pessoa, mas antes me diga o preço","mode":"request","command":null},
  {"id":"human_synonym","previous":{},"incoming":"Preciso de um atendente","mode":"request","command":"human"},
  {"id":"cancel_variant","previous":{},"incoming":"Cancelar","mode":"request","command":"cancel"},
  {"id":"cancel_variant_2","previous":{},"incoming":"Cancela isso","mode":"request","command":"cancel"},
  {"id":"opt_out_parar","previous":{},"incoming":"Parar","mode":"opt_out","command":null},
  {"id":"fragments_three","previous":{},"incoming":"Oi\nqueria saber\nvocês parcelam?","mode":"request","command":null},
  {"id":"ack_wait","previous":{"request":"Registrei sua visita."},"incoming":"ok","mode":"request","command":null,"pending":[],"last_assistant":"Registrei sua visita.","expect":"wait"},
  {"id":"ack_after_question","previous":{"request":"Qual o bairro?"},"incoming":"ok","mode":"request","command":null,"pending":["bairro"],"last_assistant":"Qual o bairro?","expect":"reply"},
  {"id":"emoji_wait","previous":{"request":"Combinado."},"incoming":"👍","mode":"request","command":null,"pending":[],"last_assistant":"Combinado.","expect":"wait"},
  {"id":"valeu_wait","previous":{"request":"Registrei."},"incoming":"valeu","mode":"request","command":null,"pending":[],"last_assistant":"Registrei.","expect":"wait"},
  {"id":"beleza_reply_after_question","previous":{"request":"Qual o bairro?"},"incoming":"beleza","mode":"request","command":null,"pending":["bairro"],"last_assistant":"Qual o bairro?","expect":"reply"},
  {"id":"short_yes","previous":{"request":"Qual o bairro?"},"incoming":"Sim","mode":"follow_up","command":null},
  {"id":"short_pode","previous":{"request":"Qual o bairro?"},"incoming":"Pode","mode":"follow_up","command":null},
  {"id":"address_question","previous":{"request":"Orçamento"},"incoming":"Qual o endereço?","mode":"request","command":null},
  {"id":"price_question","previous":{},"incoming":"Quanto custa?","mode":"request","command":null},
  {"id":"church_question","previous":{},"incoming":"Vocês atendem igreja?","mode":"request","command":null},
  {"id":"receiver_self","previous":{},"incoming":"Sou eu mesmo que vou receber","mode":"request","command":null},
  {"id":"receiver_other","previous":{},"incoming":"Outra pessoa vai receber","mode":"request","command":null},
  {"id":"name_explicit","previous":{},"incoming":"Meu nome é Ana","mode":"request","command":null},
  {"id":"address_explicit","previous":{},"incoming":"Moro na Rua das Flores, 100","mode":"request","command":null},
  {"id":"phone_explicit","previous":{},"incoming":"Meu telefone é fictício","mode":"request","command":null},
  {"id":"schedule_question","previous":{},"incoming":"Pode ser na quinta?","mode":"request","command":null}
]
```

- [ ] **Step 4: Run corpus test**

Run: `pytest tests/test_conversation_corpus.py -q`
Expected: PASS.

- [ ] **Step 5: Write consolidation record**

Create `docs/consolidacao/2026-11-12-onda1-conversacional.md` com os títulos: Escopo entregue; O que foi testado; O que é simulado; O que permanece pendente; Riscos; Como reverter. Referencie a spec e as flags. Não declarar homologação de provedor.

- [ ] **Step 6: Run full suite**

Run: `pytest -q`
Expected: PASS; registrar contagem de testes no documento de consolidação.

- [ ] **Step 7: Commit**

```bash
git add tests/fixtures/conversation_cases.json tests/test_conversation_corpus.py docs/consolidacao/2026-11-12-onda1-conversacional.md
git commit -m "Adiciona corpus conversacional e registro da onda 1"
```

---

## Self-Review

Cobertura da spec:

- Contrato estruturado e aplicação: Tasks 2 e 5.
- Memória em camadas e migration: Tasks 3, 5 e 6.
- Humanização (latência, presença, silêncio, anti-repetição): Tasks 1, 4 e 5.
- Persona: Tasks 1 e 8.
- Rotas e painel: Tasks 7 e 8.
- Testes, corpus e métricas: Tasks 2–6 e 9.
- Rollout por flag e riscos: flags em Task 1; registro em Task 9.

Tipos e nomes conferidos: `parse_decision_envelope`, `clean_visit`, `state_patch`, `contract_instructions`, `record_facts`, `memory_context`, `summary_prompt`, `delivery_plan`, `part_delay`, `should_wait`, `remember_opening`, `repeated_opening`.

Pendências deliberadas para outras ondas: ferramentas/leitura de banco, roteamento por tarefa, cotas, áudio, calendário e aprendizado automático.
