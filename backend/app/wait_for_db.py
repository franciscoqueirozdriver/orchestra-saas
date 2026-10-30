import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings


def main() -> None:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    last_error: Exception | None = None
    try:
        for _ in range(60):
            try:
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                return
            except SQLAlchemyError as exc:
                last_error = exc
                time.sleep(2)
        raise RuntimeError("PostgreSQL não ficou pronto dentro de 120 segundos") from last_error
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
