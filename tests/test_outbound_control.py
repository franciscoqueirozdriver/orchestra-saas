from app.outbound_control import outbound_is_enabled, outbound_status, set_outbound_enabled


def test_outbound_falls_back_to_environment(monkeypatch):
    monkeypatch.setattr("app.outbound_control._read_override", lambda: None)
    monkeypatch.setattr("app.outbound_control.settings.outbound_enabled", False)
    assert outbound_is_enabled() is False
    monkeypatch.setattr("app.outbound_control.settings.outbound_enabled", True)
    assert outbound_is_enabled() is True


def test_outbound_panel_override_wins(monkeypatch):
    monkeypatch.setattr("app.outbound_control.settings.outbound_enabled", False)
    monkeypatch.setattr("app.outbound_control._read_override", lambda: True)
    assert outbound_is_enabled() is True
    monkeypatch.setattr("app.outbound_control._read_override", lambda: False)
    assert outbound_is_enabled() is False


def test_outbound_status_reports_source(monkeypatch):
    monkeypatch.setattr("app.outbound_control.settings.outbound_enabled", False)
    monkeypatch.setattr("app.outbound_control._read_override", lambda: None)
    assert outbound_status() == {"enabled": False, "source": "ambiente", "environment_default": False}
    monkeypatch.setattr("app.outbound_control._read_override", lambda: True)
    assert outbound_status()["source"] == "painel"
    assert outbound_status()["enabled"] is True


def test_set_outbound_writes_redis(monkeypatch):
    stored = {}

    class FakeRedis:
        def set(self, key, value):
            stored[key] = value

    monkeypatch.setattr("app.outbound_control._client", lambda: FakeRedis())
    assert set_outbound_enabled(True) is True
    assert stored["orquestra:outbound_enabled"] == "1"
    assert set_outbound_enabled(False) is False
    assert stored["orquestra:outbound_enabled"] == "0"
