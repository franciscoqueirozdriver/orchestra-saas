from datetime import datetime,timedelta,timezone
import pytest
from app.conversation.behavior import command,wait_remaining,transition,split_reply,split_reply_conversational,output_guard,style_instructions
from app.schemas import ConversationProfile

@pytest.mark.parametrize('text,expected',[
 ('Cancela!','cancel'),('quero falar com uma pessoa','human'),('Não. Quero o endereço, não o horário',None),
 ('Bom dia, qual o horário?',None),('Não quero outra coisa',None),('qual o valor?',None)])
def test_control_commands_do_not_swallow_new_requests(text,expected):
    assert command(text)==expected


def test_maximum_wait_without_changing_last_incoming():
    now=datetime.now(timezone.utc)
    assert wait_remaining(now-timedelta(seconds=25),now,now,3,20)==0
    assert wait_remaining(now-timedelta(seconds=1),now,now,3,20)==3
    assert wait_remaining(now,now,now,0,20)==0


@pytest.mark.parametrize('text',[
 'Lista:\n\n'+('\n'.join(f'{i}. Item fictício R$ 10,00' for i in range(200))),
 'Uma frase. '*1000,'https://example.invalid/produto\n'*300,'Nome fictício e número 123.\n'*300])
def test_reply_parts_preserve_every_character(text):
    parts=split_reply(text,300)
    assert ''.join(parts)==text
    assert all(0<len(p)<=300 for p in parts)


def test_profile_changes_style_not_facts_or_permissions():
    a=ConversationProfile(enabled=True,tone='formal')
    b=ConversationProfile(enabled=True,tone='friendly')
    assert style_instructions(a,{})!=style_instructions(b,{})
    for p in (a,b):
        assert 'não é fonte de fatos' in style_instructions(p,{})
        assert 'assistente automatizado' in style_instructions(p,{})
    assert ConversationProfile().enabled is False


def test_context_carries_sales_facts_and_uses_direct_whatsapp_confirmation():
    from datetime import datetime,timezone
    from app.conversation.behavior import merge_sales_context,sales_context_instructions,apply_sales_interpretation,opportunity_ready_for_team
    now=datetime.now(timezone.utc)
    state=merge_sales_context({},'Orçamento de climatização para uma igreja pequena em Betim.',message_id='m1',captured_at=now,provider_phone='5531999999999')
    state=merge_sales_context(state,'Av. Amazonas, 1270. Centro',message_id='m2',captured_at=now)
    state=merge_sales_context(state,'Amanhã às 10:00',message_id='m3',captured_at=now)
    assert state['facts']['environment']['value']=='igreja'
    assert state['facts']['city']['value']=='Betim'
    assert state['channel_phone_status']=='unconfirmed'
    assert not opportunity_ready_for_team(state)
    state['receiver_status']='customer_confirmed'
    state['channel_phone_question_asked']=True
    assert 'return_channel_confirmation' in sales_context_instructions(state)
    state=merge_sales_context(state,'Claro.',message_id='m4',captured_at=now,last_assistant_text='Podemos usar este mesmo WhatsApp para nossa equipe entrar em contato?')
    assert state['channel_phone_status']=='unconfirmed'
    state=apply_sales_interpretation(state,{'channel_confirmation':'use_current'},message_id='m4',captured_at=now)
    assert state['channel_phone_status']=='confirmed'


def test_ambiguous_date_options_are_not_silently_collapsed():
    from datetime import datetime,timezone
    from app.conversation.behavior import merge_sales_context,sales_context_instructions
    now=datetime.now(timezone.utc)
    state=merge_sales_context({},'Pode ser amanhã ou quinta.',message_id='m1',captured_at=now)
    state['facts'].update({'city':{'value':'Betim'},'address':{'value':'Rua Sintética, 1'}})
    assert state['facts']['preferred_date']['value'].lower()=='amanhã ou quinta'
    assert 'preferred_date' in sales_context_instructions(state)
    state=merge_sales_context({},'Pode ser na próxima quinta-feira, pela manhã.',message_id='m2',captured_at=now)
    assert state['facts']['preferred_date']['value'].lower()=='na próxima quinta-feira'


def test_other_visit_receiver_requires_name_without_inventing_interlocutor():
    from datetime import datetime,timezone
    from app.conversation.behavior import merge_sales_context,sales_context_instructions,apply_sales_interpretation
    now=datetime.now(timezone.utc)
    state={'facts':{'city':{'value':'Betim'},'address':{'value':'Rua Sintética, 1'},'preferred_date':{'value':'amanhã'},'preferred_time':{'value':'10:00'}},'channel_phone_status':'confirmed','receiver_status':'unknown','receiver_question_asked':True,'appointment_status':'visit_requested'}
    state=merge_sales_context(state,'Não, minha irmã receberá.',message_id='m1',captured_at=now,last_assistant_text='Será você mesmo quem vai receber nossa equipe no local?')
    assert state['receiver_status']=='unknown'
    state=apply_sales_interpretation(state,{'receiver_confirmation':'other_person','next_required_field':'receiver_name'},message_id='m1',captured_at=now)
    assert state['receiver_status']=='other_person_needed'
    state['receiver_name_question_asked']=True
    state=apply_sales_interpretation(state,{'receiver_name':'Ana Souza'},message_id='m2',captured_at=now)
    assert state['receiver_status']=='other_person_confirmed'
    assert state['facts']['receiver_name']['value']=='Ana Souza'
    assert 'Ana Souza' in sales_context_instructions(state)
    assert 'Francisco' not in sales_context_instructions(state)
    state=merge_sales_context({'receiver_status':'other_person_needed'},'Minha irmã Ana Souza',message_id='m3',captured_at=now,
                              last_assistant_text='Qual nome devo informar?')
    assert state['receiver_status']=='other_person_needed'
    state=merge_sales_context({},'Eu mesmo, Francisco',message_id='m4',captured_at=now)
    assert state['facts']['interlocutor_name']['value']=='Francisco'


def test_appointment_preference_is_never_a_confirmed_booking_and_phone_is_redacted():
    from app.conversation.behavior import needs_unverified_visit_handoff,redact_contact_numbers
    state={'facts':{'preferred_date':{'value':'amanhã'},'preferred_time':{'value':'10:00'}}}
    assert needs_unverified_visit_handoff('A visita está confirmada para amanhã às 10h.',state)
    assert needs_unverified_visit_handoff('Perfeito, ficou marcada para quinta às 10h.',state)
    assert needs_unverified_visit_handoff('Combinado, estaremos aí na quinta.',state)
    assert not needs_unverified_visit_handoff('A visita ainda não está confirmada; falta validar.',state)
    assert not needs_unverified_visit_handoff('A visita ainda aguarda confirmação da equipe.',state)
    assert not needs_unverified_visit_handoff('A preferência ficou registrada. Será você quem vai receber a equipe amanhã?',state)
    assert '98426-5506' not in redact_contact_numbers('Telefone 31 98426-5506')


def test_legacy_humanized_profile_fields_remain_bounded_for_api_compatibility():
    default=ConversationProfile()
    assert default.visit_booking_enabled is False
    assert default.humanized_delivery is False
    assert (default.humanized_target_chars,default.humanized_max_chars,default.humanized_max_parts,default.humanized_delay_seconds)==(180,300,3,2)
    with pytest.raises(ValueError):ConversationProfile(humanized_max_parts=4)
    with pytest.raises(ValueError):ConversationProfile(humanized_max_chars=301)


def test_per_agent_style_does_not_control_global_message_delivery():
    disabled=style_instructions(ConversationProfile(enabled=True,humanized_delivery=False),{})
    enabled=style_instructions(ConversationProfile(enabled=True,humanized_delivery=True),{})
    assert disabled==enabled


def test_correction_budget_and_new_request():
    first=transition({'request':'Horário'},'Não foi isso que pedi')
    second=transition(first,'Você não entendeu')
    assert second['corrections']==2
    assert 'Não consegui' in output_guard('Pode reformular o pedido?',second)
    assert transition(second,'Agora quero o endereço')['corrections']==0
    assert transition({'request':'Horários'},'E os de amanhã?')['mode']=='follow_up'
    assert transition({},'E os de amanhã?')['previous_request']==''
    assert transition({'request':'Horário'},'Não quero outra coisa')['mode']=='new_request'


def test_output_guard_does_not_remove_factual_data():
    answer='**Itens**\nAna fictícia: R$ 10,00\nNúmero: 123456\n'
    assert output_guard(answer,{})==answer.strip()
    assert output_guard('x'*24001,{}) is None


def test_indivisible_long_item_is_refused_instead_of_truncated():
    with pytest.raises(ValueError):split_reply('https://example.invalid/'+'a'*1000,300)


def test_humanized_reply_keeps_short_answer_as_one_part():
    text='Olá! Posso ajudar com isso.'
    assert split_reply_conversational(text)==[text]


def test_visit_response_requires_model_semantics_and_rejects_untrusted_transitions():
    from app.conversation.behavior import parse_visit_response,apply_sales_interpretation
    now=datetime.now(timezone.utc)
    sales={'channel_phone_status':'unconfirmed','channel_phone_question_asked':True,'receiver_status':'unknown','receiver_question_asked':False}
    reply,updates=parse_visit_response('{"reply":"Certo, vou encaminhar sua preferência.","interpretation":{"channel_confirmation":"use_current","receiver_confirmation":"customer","receiver_name":"Xico123","next_required_field":"none"}}')
    assert reply=='Certo, vou encaminhar sua preferência.'
    assert updates=={'channel_confirmation':'use_current','receiver_confirmation':'customer','next_required_field':'none'}
    updated=apply_sales_interpretation(sales,updates,message_id='m1',captured_at=now)
    assert updated['channel_phone_status']=='confirmed'
    assert updated['receiver_status']=='unknown'  # no pending receiver question, so model cannot assert consent
    assert parse_visit_response('Resposta antiga sem envelope')==('',None)
    assert parse_visit_response('{resposta incompleta')==('',None)


def test_humanized_reply_groups_sentences_and_preserves_all_content():
    text=('A Climatiza Brasil atende empresas com soluções para diferentes ambientes e ajuda a identificar '
          'uma alternativa adequada para cada espaço. Para entender seu caso, qual é a metragem aproximada '
          'do ambiente? Podemos verificar uma visita para avaliação?')
    parts=split_reply_conversational(text)
    assert len(parts)>1
    assert ''.join(parts)==text
    assert all(0<len(part)<=300 for part in parts)
    assert all(part==part.strip() or part.endswith((' ', '\n')) for part in parts)
    assert split_reply_conversational(text,max_parts=1)==[text]


def test_humanized_reply_preserves_url_phone_and_price_as_units():
    url='https://example.invalid/catalogo/modelo-abc'
    phone='11 99999-9999'
    price='R$ 1.250,00'
    text=('Para receber os detalhes completos do equipamento e combinar a avaliação do espaço, '
          f'acesso {url} ou fale com nossa equipe pelo telefone {phone}. '
          f'O valor de referência informado foi {price}; confirme as condições antes de fechar. '
          'Nossa equipe pode verificar a visita mais adequada para sua empresa.')
    parts=split_reply_conversational(text)
    assert ''.join(parts)==text
    assert all(0<len(part)<=300 for part in parts)
    assert sum(url in part for part in parts)==1
    assert sum(phone in part for part in parts)==1
    assert sum(price in part for part in parts)==1


def test_humanized_reply_refuses_to_truncate_when_three_parts_are_not_enough():
    text=' '.join(f'Frase completa número {i} com conteúdo suficiente para explicar o próximo passo.' for i in range(1, 16))
    with pytest.raises(ValueError,match='máximo seguro de partes'):
        split_reply_conversational(text)


@pytest.mark.parametrize('kwargs', [
    {'target_chars':99}, {'target_chars':181}, {'max_chars':301}, {'max_parts':4}, {'target_chars':250,'max_chars':200},
])
def test_humanized_reply_enforces_backend_limits(kwargs):
    with pytest.raises(ValueError):
        split_reply_conversational('Esta é uma resposta sintética suficientemente longa para validar os limites.',**kwargs)


import json
from pathlib import Path
CASES=json.loads((Path(__file__).parent/'fixtures/conversation_cases.json').read_text())


@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_synthetic_conversation_corpus_policy_only(case):
    assert command(case['incoming'])==case['command']
    assert transition(case['previous'],case['incoming'])['mode']==case['mode']


def test_repeated_clarification_is_limited_even_without_explicit_correction():
    from app.conversation.behavior import CLARIFICATION_LIMIT_REPLY
    state=transition({'request':'Pedido ambíguo','clarifications':1},'Isso aí')
    assert output_guard('Pode explicar melhor?',state)==CLARIFICATION_LIMIT_REPLY
    again=transition({**state,'limit_notified':True},'Não sei')
    assert output_guard('Poderia reformular?',again) is None
    assert output_guard('A informação fictícia está confirmada na fonte.',again)=='A informação fictícia está confirmada na fonte.'
    assert transition(again,'Agora quero o endereço')['clarifications']==0


@pytest.mark.parametrize('identifier',[None,{}, {'unexpected':'synthetic'},True,123,'x'*181,'bad\nidentifier'])
def test_transport_rejects_malformed_receipt_ids(identifier):
    from types import SimpleNamespace
    from app.transport import ZapiTransport
    adapter=ZapiTransport.__new__(ZapiTransport)
    adapter.client=SimpleNamespace(send_text=lambda *args:{'messageId':identifier})
    assert adapter.send_text('synthetic-contact','synthetic message').message_id is None


@pytest.mark.parametrize('adapter_name', ['ZapiTransport','WameTransport'])
def test_provider_adapters_keep_presence_disabled_and_send_part_contract(adapter_name):
    from types import SimpleNamespace
    from app import transport
    adapter_type=getattr(transport,adapter_name)
    adapter=adapter_type.__new__(adapter_type)
    adapter.client=SimpleNamespace(send_text=lambda destination,text:{'messageId':'synthetic-provider-receipt'})
    receipt=adapter.send_text('synthetic-contact','Parte sintética.')
    assert receipt.message_id=='synthetic-provider-receipt'
    assert adapter.composing('synthetic-contact') is False
