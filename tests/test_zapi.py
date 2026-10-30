import json

import pytest

from app.zapi_client import ZapiClient
from app.zapi_payload import classify, contact_key, event_key


TEXT_CALLBACK = {
    "instanceId": "INSTANCE-1",
    "messageId": "MSG-1",
    "phone": "5511999999999",
    "senderLid": "81896604192873@lid",
    "fromMe": False,
    "isGroup": False,
    "type": "ReceivedCallback",
    "text": {"message": "Oi, queria uma informação"},
}


def test_received_text_callback_fields():
    assert classify(TEXT_CALLBACK) == ("text", "Oi, queria uma informação")
    assert contact_key(TEXT_CALLBACK) == "81896604192873@lid"
    assert event_key(TEXT_CALLBACK) == "MSG-1"


def test_event_key_stable_without_external_message_id():
    first = {"phone": "5511999999999", "type": "ReceivedCallback"}
    assert event_key(first) == event_key(json.loads(json.dumps(first)))


def test_media_callback_does_not_claim_text_support():
    kind, content = classify({"image": {"imageUrl": "https://private-media.test/image.jpg"}})
    assert kind == "image"
    assert "não processado" in content


def test_send_text_builds_documented_endpoint_and_headers(monkeypatch):
    captured = {}

    class FakeResponse:
        is_success = True
        content = b'{"zaapId":"z1","messageId":"m1"}'
        text = content.decode()
        status_code = 200
        def json(self):
            return {"zaapId": "z1", "messageId": "m1"}

    def fake_request(method, url, **kwargs):
        captured.update(method=method, url=url, **kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.zapi_client.httpx.request", fake_request)
    result = ZapiClient("INSTANCE-1", "TOKEN-1", "CLIENT-1").send_text("5511999999999", "Olá")
    assert result["messageId"] == "m1"
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/instances/INSTANCE-1/token/TOKEN-1/send-text")
    assert captured["headers"]["Client-Token"] == "CLIENT-1"
    assert captured["json"] == {"phone": "5511999999999", "message": "Olá"}


def test_send_text_rejects_invalid_destination():
    with pytest.raises(ValueError):
        ZapiClient("i", "t").send_text("+55 (11) 99999-9999", "Oi")
