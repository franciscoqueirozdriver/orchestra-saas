"""One Beat leader per database, with a heartbeat and no application data access."""
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from sqlalchemy import text

HEARTBEAT = Path('/tmp/orchestra-scheduler-heartbeat')


def healthy():
    try:
        return 0 <= time.time() - float(HEARTBEAT.read_text()) < 45
    except (OSError, ValueError):
        return False


def main():
    from app.database import engine
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    # Hold the exact connection as leader; if its heartbeat fails, terminate Beat.
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
        acquired = connection.execute(text("SELECT pg_try_advisory_lock(hashtextextended('orchestra:beat-leader',0))")).scalar()
        if not acquired:
            print('Scheduler já tem líder; segunda instância recusada.', flush=True)
            return 75
        child = None
        try:
            child = subprocess.Popen([sys.executable, '-m', 'celery', '-A', 'app.tasks.celery_app', 'beat',
                                      '--loglevel=INFO', '--schedule=/tmp/orchestra-celerybeat'])
            while not stop.is_set() and child.poll() is None:
                connection.execute(text('SELECT 1'))
                HEARTBEAT.write_text(str(time.time()))
                stop.wait(5)
            return 0 if stop.is_set() else (child.returncode or 1)
        finally:
            HEARTBEAT.unlink(missing_ok=True)
            if child and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            connection.execute(text("SELECT pg_advisory_unlock(hashtextextended('orchestra:beat-leader',0))"))


if __name__ == '__main__':
    if '--health' in sys.argv:
        sys.exit(0 if healthy() else 1)
    sys.exit(main())
