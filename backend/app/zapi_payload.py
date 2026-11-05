from hashlib import sha256
import json
from typing import Any


def event_key(payload: dict[str, Any]) -> str:
    if payload.get("type") == "MessageStatusCallback":
        canonical = json.dumps({"ids": sorted(str(x) for x in payload.get("ids", [])), "status": payload.get("status"), "type": payload.get("type")}, sort_keys=True)
        return sha256(canonical.encode()).hexdigest()
    message_id = payload.get("messageId") or payload.get("zaapId") or payload.get("id")
    if message_id:
        return str(message_id)[:220]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()


def classify(payload: dict[str, Any]) -> tuple[str, str]:
    # A Z-API usa type=ReceivedCallback e um objeto especializado conforme a mídia.
    for kind in ("text", "image", "audio", "video", "document", "contact", "location", "sticker", "reaction", "poll", "listResponse", "buttonReply"):
        value = payload.get(kind)
        if isinstance(value, dict):
            if kind == "text":
                message = value.get("message")
                if isinstance(message, str):
                    return "text", message[:12000]
                return "text", ""
            caption = value.get("caption")
            if isinstance(caption, str) and caption.strip():
                return kind, caption[:12000]
            return kind, f"[{kind} recebida — conteúdo não processado nesta versão]"
    return "unknown", "[Evento recebido — tipo ainda não processado]"


def from_me(payload: dict[str, Any]) -> bool:
    return payload.get("fromMe") is True or str(payload.get("fromMe", "")).strip().lower() in {"true", "1"}


def contact_key(payload: dict[str, Any]) -> str:
    # Preserva LID/identificadores originais quando presentes; sempre vinculado à instância.
    return str(payload.get("chatLid") or payload.get("senderLid") or payload.get("phone") or payload.get("participantLid") or payload.get("participantPhone") or "")[:180]


def contact_name(payload: dict[str, Any]) -> str:
    return str(payload.get("senderName") or payload.get("chatName") or "")[:180]
