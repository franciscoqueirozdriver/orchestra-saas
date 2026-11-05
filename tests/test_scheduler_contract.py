from pathlib import Path
import time
import yaml
from app import scheduler


def test_scheduler_heartbeat_expires_and_does_not_treat_missing_as_healthy(tmp_path, monkeypatch):
    heartbeat = tmp_path / 'heartbeat'
    monkeypatch.setattr(scheduler, 'HEARTBEAT', heartbeat)
    assert not scheduler.healthy()
    heartbeat.write_text(str(time.time()))
    assert scheduler.healthy()
    heartbeat.write_text(str(time.time()-60))
    assert not scheduler.healthy()


def test_compose_uses_one_image_and_one_separate_scheduler():
    root = Path(__file__).resolve().parents[1]
    services = yaml.safe_load((root/'docker-compose.yml').read_text())['services']
    assert services['api']['image'] == services['worker']['image'] == services['scheduler']['image']
    assert 'build' not in services['worker'] and 'build' not in services['scheduler']
    assert services['scheduler']['command'] == ['python', '-m', 'app.scheduler']
    assert services['scheduler']['environment']['RUN_MIGRATIONS'] == 'false'
    assert services['scheduler']['environment']['OUTBOUND_ENABLED'] == '${OUTBOUND_ENABLED:-false}'
    assert services['scheduler']['depends_on']['api']['condition'] == 'service_healthy'


def test_scheduler_terminates_beat_if_database_heartbeat_fails(tmp_path, monkeypatch):
    import pytest
    from app import database
    class Result:
        def scalar(self): return True
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execution_options(self, **kw): return self
        def execute(self, statement):
            if str(statement) == 'SELECT 1':
                raise RuntimeError('synthetic connection loss')
            return Result()
    class Engine:
        def connect(self): return Connection()
    class Child:
        terminated = False
        def poll(self): return None
        def terminate(self): self.terminated = True
        def wait(self, **kw): return 0
    child = Child()
    monkeypatch.setattr(database, 'engine', Engine())
    monkeypatch.setattr(scheduler.signal, 'signal', lambda *a: None)
    monkeypatch.setattr(scheduler.subprocess, 'Popen', lambda *a, **kw: child)
    monkeypatch.setattr(scheduler, 'HEARTBEAT', tmp_path/'heartbeat')
    with pytest.raises(RuntimeError, match='synthetic connection loss'):
        scheduler.main()
    assert child.terminated
