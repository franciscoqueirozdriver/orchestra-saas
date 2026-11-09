import pytest
from pydantic import ValidationError

from app.schemas import ZapiInstanceCreate
from app.wame_client import WameClient
from app.wame_payload import normalize_wame_events
from app.zapi_payload import classify, contact_key, from_me


OFFICIAL_TEXT = {
    "object": "wame",
    "provider": "whatsapp",
    "instance": "remote-instance",
    "official": True,
    "entry": [{
        "id": "000",
        "changes": [{
            "field": "messages",
            "value": {
                "messaging_product": "whatsapp",
                "contacts": [{"profile": {"name": "Cliente"}, "wa_id": "5511988887777"}],
                "messages": [{
                    "from": "5511988887777",
                    "id": "wamid.TEXT",
                    "timestamp": "1700000000",
                    "text": {"body": "Olá"},
                    "type": "text",
                }],
            },
        }],
    }],
}

QR_TEXT = {
    "object": "wame",
    "provider": "whatsapp",
    "official": False,
    "entry": [{
        "changes": [{
            "field": "messages",
            "value": {
                "messaging_product": "whatsapp",
                "contacts": [{"profile": {"name": "Fulano"}, "wa_id": "5511999998888"}],
                "messages": [{
                    "from": "5511999998888",
                    "chat_type": "individual",
                    "id": "WAMID_TEXT",
                    "type": "text",
                    "text": {"body": "Olá!"},
                }],
            },
        }],
    }],
}


def test_alternative_provider_is_accepted_and_unknown_is_not():
    created = ZapiInstanceCreate(provider="wame", label="Loja", instance_id="loja-01", token="chave-da-instancia")
    assert created.provider == "wame"
    assert created.client_token is None
    qr = ZapiInstanceCreate(provider="wame_qr", label="Loja", instance_id="loja-01", token="chave-da-instancia", client_token="nao-usar")
    official = ZapiInstanceCreate(provider="wame_official", label="Loja", instance_id="loja-01", token="chave-da-instancia")
    assert qr.provider == "wame_qr" and qr.client_token is None
    assert official.provider == "wame_official"
    with pytest.raises(ValidationError):
        ZapiInstanceCreate(provider="outro", label="Loja", instance_id="loja-01", token="chave-da-instancia")
    with pytest.raises(ValidationError):
        ZapiInstanceCreate(provider="zapi_official", label="Loja", instance_id="loja-01", token="chave-da-instancia")


def test_both_wame_models_use_the_wame_connector():
    from app.transport import is_wame_provider

    assert is_wame_provider("wame") and is_wame_provider("wame_qr") and is_wame_provider("wame_official")
    assert is_wame_provider("zapi") is False


def test_official_and_qr_text_become_the_same_internal_event():
    official = normalize_wame_events(OFFICIAL_TEXT)[0]
    qr = normalize_wame_events(QR_TEXT)[0]
    assert "official" not in official and "official" not in qr
    assert classify(official) == ("text", "Olá")
    assert classify(qr) == ("text", "Olá!")
    assert from_me(official) is False
    assert contact_key(official) == "5511988887777"
    assert official["type"] == qr["type"] == "ReceivedCallback"
    assert official["isGroup"] is False


def test_group_from_me_and_delivery_keep_existing_pipeline_fields():
    group = normalize_wame_events({
        "object": "wame", "provider": "whatsapp", "official": False,
        "entry": [{"changes": [{"field": "messages", "value": {"messages": [{
            "from": "5511777776666", "chat_type": "group",
            "group_id": "16479379001-1580667835@g.us", "id": "WAMID_GRP",
            "type": "text", "text": {"body": "oi grupo"},
        }]}}]}],
    })[0]
    assert group["isGroup"] is True
    assert group["phone"] == "16479379001-1580667835@g.us"
    assert group["participantPhone"] == "5511777776666"

    own = normalize_wame_events({
        "object": "wame", "provider": "whatsapp",
        "entry": [{"changes": [{"field": "messages", "value": {"messages": [{
            "from": "5511999998888", "chat_type": "individual", "id": "WAMID_OUT",
            "type": "text", "text": {"body": "ASSUMINDO 123456"}, "from_me": True,
        }]}}]}],
    })[0]
    assert from_me(own) is True
    assert classify(own) == ("text", "ASSUMINDO 123456")

    delivered = normalize_wame_events({
        "object": "wame", "provider": "whatsapp", "official": True,
        "entry": [{"changes": [{"field": "messages", "value": {"statuses": [{
            "id": "WAMID_TEXT", "status": "delivered", "recipient_id": "5511999998888",
        }]}}]}],
    })[0]
    assert delivered["type"] == "MessageStatusCallback"
    assert delivered["status"] == "RECEIVED"
    assert delivered["ids"] == ["WAMID_TEXT"]


def test_other_channels_and_connection_events_do_not_enter_the_desk():
    assert normalize_wame_events({"object": "wame", "provider": "instagram", "official": True, "entry": []}) == []
    assert normalize_wame_events({"object": "wame", "provider": "telegram", "entry": [{"changes": [{"field": "messages"}]}]}) == []
    assert normalize_wame_events({
        "object": "wame", "provider": "whatsapp",
        "entry": [{"changes": [{"field": "connection", "value": {"status": "open"}}]}],
    }) == []


def test_send_status_webhook_and_group_use_one_contract(monkeypatch):
    captured = []

    class FakeResponse:
        def __init__(self, payload):
            self.is_success = True
            self.status_code = 200
            self._payload = payload
            self.content = b"{}"
        def json(self):
            return self._payload

    def fake_request(method, url, **kwargs):
        captured.append((method, url, kwargs.get("json")))
        if url.endswith("/message/text"):
            return FakeResponse({"status": 200, "data": {"key": {"id": "3EB0", "remoteJid": "5511@s.whatsapp.net", "fromMe": True}}})
        if url.endswith("/instance") and method == "GET":
            return FakeResponse({"status": 200, "instance": {"phoneConnected": True, "blocked": False}})
        if url.endswith("/groups"):
            return FakeResponse({"status": 200, "data": {"id": "120363000@g.us"}})
        return FakeResponse({"status": 200})

    monkeypatch.setattr("app.wame_client.httpx.request", fake_request)
    client = WameClient("chave-secreta")
    assert client.send_text("5511999998888", "Oi")["messageId"] == "3EB0"
    assert client.status() == {"connected": True, "smartphoneConnected": True}
    assert client.create_group("Equipe", ["5511999998888"])["phone"] == "120363000@g.us"
    client.configure_webhooks("https://app.example/api/webhooks/zapi/loja/segredo")

    send = captured[0]
    assert send[0] == "POST"
    assert send[1].endswith("/chave-secreta/message/text")
    assert send[2] == {"to": "5511999998888", "text": "Oi", "provider": "whatsapp"}
    webhook = captured[-1][2]
    assert webhook["webhookFormat"] == "meta"
    assert webhook["webhookMessage"] == webhook["webhookMessageFromMe"] == webhook["webhookGroup"]
    assert "webhookHistory" not in webhook
