"""Deterministic outbound controls; models cannot override these decisions."""
from datetime import datetime, timedelta, timezone
import re
import unicodedata

def is_opt_out(text: str) -> bool:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = re.sub(r"[^a-z0-9 ]", " ", normalized)
    normalized = " ".join(normalized.split())
    return normalized in {"sair", "parar", "stop", "cancelar mensagens", "nao quero receber mensagens", "pare de me enviar mensagens", "nao me envie mais mensagens", "remover meu numero", "descadastrar"}

def sending_denial(instance, conversation, now: datetime | None = None) -> str | None:
    now = now or datetime.now(timezone.utc)
    if not instance or not instance.is_active or not instance.sending_enabled:
        return "instance_paused"
    if instance.status != "connected":
        return "instance_disconnected"
    if not conversation or conversation.opted_out or conversation.consent_status == "denied":
        return "contact_blocked"
    if conversation.status != "open":
        return "conversation_paused"
    if conversation.consent_status == "granted":
        return None
    incoming = conversation.last_incoming_at
    if incoming and incoming.tzinfo is None:
        incoming = incoming.replace(tzinfo=timezone.utc)
    # Internal policy for responding to user-initiated support, not a Z-API/WhatsApp guarantee.
    if incoming and timedelta(0) <= now - incoming <= timedelta(hours=24):
        return None
    return "consent_required"

STATUS_RANK = {"accepted": 0, "sent": 1, "delivered": 2, "read": 3, "played": 4}
def advance_status(current: str, candidate: str) -> str:
    if candidate in STATUS_RANK and STATUS_RANK[candidate] > STATUS_RANK.get(current, -1):
        return candidate
    if candidate == "failed" and current not in {"delivered", "read", "played"}:
        return candidate
    return current
