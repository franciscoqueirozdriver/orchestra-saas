"""PostgreSQL session locks survive commits and do not expire during external I/O.

All supported writers and dispatchers serialize per tenant. Generation uses a
separate conversation lock and rechecks its revision before enqueue. This favors
correctness over throughput for the first controlled release.
"""
from contextlib import contextmanager
from sqlalchemy import text
from app.database import engine


@contextmanager
def advisory_guard(key, *, blocking=True, bind=None):
    connection = (bind or engine).connect().execution_options(isolation_level='AUTOCOMMIT')
    acquired = False
    try:
        fn = 'pg_advisory_lock' if blocking else 'pg_try_advisory_lock'
        result = connection.execute(text(f'SELECT {fn}(hashtextextended(:key, 0))'), {'key': key}).scalar()
        acquired = True if blocking else bool(result)
        yield acquired
    finally:
        if acquired:
            try:
                connection.execute(text('SELECT pg_advisory_unlock(hashtextextended(:key, 0))'), {'key': key})
            except Exception:
                connection.invalidate()
        connection.close()


def tenant_guard(tenant_id, *, blocking=True):
    return advisory_guard('orchestra:tenant:' + tenant_id, blocking=blocking)
