"""Runtime outbound arming. Redis override when set; otherwise OUTBOUND_ENABLED."""
from redis import Redis
from redis.exceptions import RedisError

from app.config import settings

REDIS_KEY = "orquestra:outbound_enabled"


def _client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)


def _read_override() -> bool | None:
    try:
        value = _client().get(REDIS_KEY)
    except RedisError:
        return None
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def outbound_is_enabled() -> bool:
    override = _read_override()
    if override is not None:
        return override
    return bool(settings.outbound_enabled)


def set_outbound_enabled(enabled: bool) -> bool:
    try:
        _client().set(REDIS_KEY, "1" if enabled else "0")
    except RedisError as exc:
        raise RuntimeError("Não foi possível gravar a liberação de envio") from exc
    return enabled


def outbound_status() -> dict:
    override = _read_override()
    return {
        "enabled": outbound_is_enabled(),
        "source": "painel" if override is not None else "ambiente",
        "environment_default": bool(settings.outbound_enabled),
    }
