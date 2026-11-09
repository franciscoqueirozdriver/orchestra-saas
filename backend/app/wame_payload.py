"""Translate the shared official/QR webhook envelope into the internal event shape.

Both connection models use the same Meta-style envelope. `official` only records
which model produced the event and does not change parsing. Channels other than
WhatsApp are acknowledged by the caller and not turned into desk conversations.
"""
from typing import Any


_STATUS = {
    "sent": "SENT",
    "delivered": "RECEIVED",
    "read": "READ",
    "played": "PLAYED",
}
_MEDIA = ("image", "audio", "video", "document", "sticker", "location", "reaction")


def is_wame_envelope(payload: dict[str, Any]) -> bool:
    return payload.get("object") == "wame"


def normalize_wame_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not is_wame_envelope(payload):
        return []
    if str(payload.get("provider") or "whatsapp") != "whatsapp":
        return []
    events: list[dict[str, Any]] = []
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict) or change.get("field") != "messages":
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            product = value.get("messaging_product")
            if product not in (None, "whatsapp"):
                continue
            names = _contact_names(value.get("contacts"))
            for message in value.get("messages") or []:
                if isinstance(message, dict):
                    events.append(_message_event(message, names))
            for status in value.get("statuses") or []:
                if isinstance(status, dict):
                    event = _status_event(status)
                    if event:
                        events.append(event)
            if len(events) >= 50:
                return events[:50]
    return events


def _contact_names(contacts: Any) -> dict[str, str]:
    names: dict[str, str] = {}
    if not isinstance(contacts, list):
        return names
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        wa_id = str(contact.get("wa_id") or "").strip()
        profile = contact.get("profile") if isinstance(contact.get("profile"), dict) else {}
        if wa_id:
            names[wa_id] = str(profile.get("name") or "")[:180]
    return names


def _message_event(message: dict[str, Any], names: dict[str, str]) -> dict[str, Any]:
    sender = str(message.get("from") or "").strip()
    group_id = str(message.get("group_id") or "").strip()
    grouped = message.get("chat_type") == "group" or bool(group_id)
    event: dict[str, Any] = {
        "type": "ReceivedCallback",
        "messageId": message.get("id"),
        "fromMe": message.get("from_me") is True,
        "isGroup": grouped,
        "senderName": names.get(sender, ""),
    }
    if grouped:
        event["phone"] = group_id or sender
        event["participantPhone"] = sender
        if group_id:
            event["chatLid"] = group_id
    else:
        event["phone"] = sender
    kind = str(message.get("type") or "text")
    if kind == "text":
        body = message.get("text") if isinstance(message.get("text"), dict) else {}
        event["text"] = {"message": str(body.get("body") or "")}
    elif kind in _MEDIA:
        media = message.get(kind) if isinstance(message.get(kind), dict) else {}
        event[kind] = {"caption": str(media.get("caption") or "")}
    return event


def _status_event(status: dict[str, Any]) -> dict[str, Any] | None:
    identifier = status.get("id")
    if not isinstance(identifier, (str, int)) or isinstance(identifier, bool) or not str(identifier).strip():
        return None
    raw = str(status.get("status") or "").strip().lower()
    mapped = _STATUS.get(raw)
    if mapped is None and raw != "failed":
        return None
    event: dict[str, Any] = {
        "type": "MessageStatusCallback",
        "ids": [str(identifier)],
        "status": mapped or "SENT",
        "messageId": identifier,
    }
    if raw == "failed":
        event["error"] = True
    return event
