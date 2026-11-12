import pytest

from app.llm_client import LLMError
from app.schemas import ConversationProfile
from app.tasks import _conversation_validator

VALID = ('{"reply":"Claro, Ana. Qual o bairro?",'
         '"decision":{"intent":"pedido","sentiment":"neutro","stage":"coletando",'
         '"action":"respond","facts":{"interlocutor_name":"Ana"},'
         '"pending":["confirmar bairro"],"next_best_action":"perguntar bairro"}}')


def test_decision_validator_accepts_only_the_conversational_envelope():
    validate = _conversation_validator(ConversationProfile(enabled=True, structured_decision_enabled=True))
    validate(VALID)
    with pytest.raises(LLMError) as exc:
        validate('Resposta comum em texto.')
    assert exc.value.category == 'invalid_response'


def test_decision_validator_rejects_malformed_visit_interpretation_for_visit_agents():
    profile = ConversationProfile(enabled=True, structured_decision_enabled=True, visit_booking_enabled=True)
    validate = _conversation_validator(profile)
    validate(VALID)
    with pytest.raises(LLMError) as exc:
        validate(VALID[:-1] + ',"visit":{"channel_confirmation":"talvez"}}')
    assert exc.value.category == 'invalid_response'
