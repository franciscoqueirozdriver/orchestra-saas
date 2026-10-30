from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.dependencies import get_tenant_id
from app.llm_client import complete
from app.models import Tenant
from app.routes_zapi import _minimize_payload
from app.url_safety import UnsafeExternalURL, validate_public_https


def test_groq_completion_uses_text_only_chat_completions(monkeypatch):
    captured = {}
    def fake_post(url, api_key, payload):
        captured.update(url=url, api_key=api_key, payload=payload)
        return {"choices": [{"message": {"content": "Resposta"}}]}
    monkeypatch.setattr("app.llm_client._post", fake_post)
    answer = complete("groq", "https://api.groq.com/openai/v1", "model-x", "secret", "Instruções", [{"role": "user", "content": "Oi"}])
    assert answer == "Resposta"
    assert captured["url"].endswith("/chat/completions")
    assert "tools" not in captured["payload"]


def test_xai_responses_api_is_text_only(monkeypatch):
    captured = {}
    def fake_post(url, api_key, payload):
        captured.update(url=url, payload=payload)
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": "Olá"}]}]}
    monkeypatch.setattr("app.llm_client._post", fake_post)
    answer = complete("xai", "https://api.x.ai/v1", "grok-model", "secret", "Instruções", [{"role": "user", "content": "Oi"}])
    assert answer == "Olá"
    assert captured["url"].endswith("/responses")
    assert "tools" not in captured["payload"]


def test_media_callback_minimizes_private_urls():
    safe = _minimize_payload({"instanceId": "i", "type": "ReceivedCallback", "phone": "5511999999999", "image": {"imageUrl": "https://secret.invalid/photo", "caption": "caption"}})
    assert "imageUrl" not in safe
    assert safe["normalizedKind"] == "image"


class FakeQuery:
    def __init__(self, value):
        self.value = value
    def filter(self, *args):
        return self
    def first(self):
        return self.value


class FakeDB:
    def __init__(self, value=None):
        self.value = value
    def query(self, _model):
        return FakeQuery(self.value)


def test_tenant_admin_cannot_select_another_tenant():
    user = SimpleNamespace(role="tenant_admin", tenant_id="tenant-a")
    with pytest.raises(HTTPException) as error:
        get_tenant_id(FakeDB(SimpleNamespace(id="tenant-a")), user, "tenant-b")
    assert error.value.status_code == 403


def test_platform_admin_must_select_existing_active_tenant():
    user = SimpleNamespace(role="platform_admin", tenant_id=None)
    with pytest.raises(HTTPException) as error:
        get_tenant_id(FakeDB(), user, None)
    assert error.value.status_code == 400
    assert get_tenant_id(FakeDB(SimpleNamespace(id="tenant-a")), user, "tenant-a") == "tenant-a"


def test_private_or_local_provider_host_is_rejected(monkeypatch):
    monkeypatch.setattr("app.url_safety.socket.getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 443))])
    with pytest.raises(UnsafeExternalURL):
        validate_public_https("https://provider.example/v1")
