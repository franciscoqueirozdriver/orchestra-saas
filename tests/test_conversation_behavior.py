from datetime import datetime,timedelta,timezone
import pytest
from app.conversation.behavior import command,wait_remaining,transition,split_reply,output_guard,style_instructions
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
