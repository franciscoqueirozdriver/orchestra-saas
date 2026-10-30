import pytest
from pydantic import ValidationError

from app.schemas import LLMConfigUpsert, ZapiInstanceCreate


def test_provider_base_url_is_required_and_https():
    with pytest.raises(ValidationError):
        LLMConfigUpsert(provider="groq", base_url="", model="model", api_key="secret")
    with pytest.raises(ValidationError):
        LLMConfigUpsert(provider="groq", base_url="http://api.groq.com/openai/v1", model="model", api_key="secret")


def test_embedding_base_url_is_optional_but_https_when_set():
    config = LLMConfigUpsert(provider="xai", base_url="https://api.x.ai/v1", model="grok-model", embedding_base_url="", api_key="secret")
    assert config.embedding_base_url is None
    with pytest.raises(ValidationError):
        LLMConfigUpsert(provider="xai", base_url="https://api.x.ai/v1", model="grok-model", embedding_base_url="https://example.com/v1?x=1", api_key="secret")


def test_instance_id_rejects_path_separators():
    with pytest.raises(ValidationError):
        ZapiInstanceCreate(label="Principal", instance_id="id/../../callback", token="token-secret")
