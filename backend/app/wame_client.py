from urllib.parse import quote, urlparse
import logging

# The instance key is part of the URL. Keep request URLs out of info logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

import httpx

from app.config import settings
from app.zapi_client import ZapiError


class WameError(ZapiError):
    def __init__(self, status_code: int, message: str = "") -> None:
        self.status_code = status_code
        self.message = message
        RuntimeError.__init__(self, "Falha na conexão remota" + (f": {message}" if message else ""))


class WameClient:
    """One client for the official channel and the QR connection.

    The remote contract is the same. The key stays in the request path and is
    never placed in the public webhook URL.
    """

    def __init__(self, key: str) -> None:
        self.key = key.strip()
        if not self.key or any(ch in self.key for ch in "/?# \t\r\n"):
            raise ValueError("A chave da instância é inválida")
        self.timeout = httpx.Timeout(25.0, connect=8.0)

    def _url(self, suffix: str) -> str:
        return f"{settings.wame_api_base_url}/{quote(self.key, safe='')}/{suffix.lstrip('/')}"

    def _request(self, method: str, suffix: str, *, json: dict | None = None) -> dict:
        try:
            response = httpx.request(
                method, self._url(suffix),
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json=json, timeout=self.timeout, follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            raise WameError(0, "Falha de rede ao consultar a conexão") from exc
        if not response.is_success:
            raise WameError(response.status_code)
        if not response.content:
            return {}
        try:
            data = response.json()
            return data if isinstance(data, dict) else {"data": data}
        except ValueError:
            return {}

    def send_text(self, phone: str, message: str) -> dict:
        destination = phone.strip()
        if not destination or any(c not in "0123456789@._-abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in destination):
            raise ValueError("Informe telefone apenas com dígitos, ou o identificador de grupo da conexão")
        remote = self._request("POST", "message/text", json={"to": destination, "text": message, "provider": "whatsapp"})
        data = remote.get("data") if isinstance(remote.get("data"), dict) else {}
        key = data.get("key") if isinstance(data.get("key"), dict) else {}
        identifier = key.get("id") or data.get("id") or remote.get("id")
        return {"messageId": identifier} if identifier else {}

    def create_group(self, group_name: str, phones: list[str], *, auto_invite: bool = False) -> dict:
        del auto_invite  # Participants are added by the create call; there is no separate private-invite flag.
        if not group_name.strip() or not phones:
            raise ValueError("Informe o nome do grupo e pelo menos um participante")
        normalized = []
        for phone in phones:
            digits = "".join(ch for ch in str(phone) if ch.isdigit())
            if not 10 <= len(digits) <= 15:
                raise ValueError("Telefone de participante inválido")
            if digits not in normalized:
                normalized.append(digits)
        remote = self._request("POST", "groups", json={"name": group_name.strip(), "participants": normalized})
        return {"phone": _group_id(remote)}

    def status(self) -> dict:
        remote = self._request("GET", "instance")
        instance = remote.get("instance") if isinstance(remote.get("instance"), dict) else {}
        connected = False
        for source in (instance, remote):
            if source.get("blocked") is True:
                connected = False
                break
            if source.get("phoneConnected") is True or source.get("connected") is True:
                connected = True
                break
        return {"connected": connected, "smartphoneConnected": connected}

    def configure_webhooks(self, callback_url: str) -> dict:
        parsed = urlparse(callback_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Webhook deve usar HTTPS sem credenciais embutidas")
        return self._request("PUT", "instance", json={
            "allowWebhook": True,
            "allowNumber": "all",
            "webhookFormat": "meta",
            "webhookMessage": callback_url,
            "webhookGroup": callback_url,
            "webhookMessageFromMe": callback_url,
        })


def _group_id(remote: dict) -> str:
    found = _find_group_id(remote)
    return found or ""


def _find_group_id(value, depth: int = 0) -> str:
    if depth > 4:
        return ""
    if isinstance(value, str):
        text = value.strip()
        return text if text.endswith("@g.us") else ""
    if isinstance(value, dict):
        for key in ("id", "gid", "phone", "groupId", "remoteJid"):
            found = _find_group_id(value.get(key), depth + 1)
            if found:
                return found
        for key in ("data", "group", "key"):
            found = _find_group_id(value.get(key), depth + 1)
            if found:
                return found
    if isinstance(value, list):
        for item in value[:20]:
            found = _find_group_id(item, depth + 1)
            if found:
                return found
    return ""
