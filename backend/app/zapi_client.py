from urllib.parse import quote
import logging

# httpx INFO includes request URLs; Z-API places credentials in its path.
logging.getLogger("httpx").setLevel(logging.WARNING)

import httpx

from app.config import settings


class ZapiError(RuntimeError):
    def __init__(self, status_code: int, message: str = "") -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"Z-API retornou HTTP {status_code}" + (f": {message}" if message else ""))


class ZapiClient:
    def __init__(self, instance_id: str, token: str, client_token: str | None = None) -> None:
        self.instance_id = instance_id
        self.token = token
        self.client_token = client_token
        self.timeout = httpx.Timeout(25.0, connect=8.0)

    def _url(self, suffix: str) -> str:
        instance = quote(self.instance_id, safe="")
        token = quote(self.token, safe="")
        return f"{settings.zapi_api_base_url}/instances/{instance}/token/{token}/{suffix.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.client_token:
            headers["Client-Token"] = self.client_token
        return headers

    def _request(self, method: str, suffix: str, *, json: dict | None = None) -> dict:
        try:
            response = httpx.request(method, self._url(suffix), headers=self._headers(), json=json, timeout=self.timeout, follow_redirects=False)
        except httpx.HTTPError as exc:
            raise ZapiError(0, "Falha de rede ao conectar à Z-API; confira a configuração e tente novamente") from exc
        if not response.is_success:
            # Não devolver corpo remoto: evita eco de tokens/payloads nos erros exibidos ao operador.
            raise ZapiError(response.status_code)
        if not response.content:
            return {}
        try:
            data = response.json()
            return data if isinstance(data, dict) else {"data": data}
        except ValueError:
            return {"response_text": response.text[:500]}

    def send_text(self, phone: str, message: str) -> dict:
        normalized = phone.strip()
        if not normalized or any(c not in "0123456789@._-abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in normalized):
            raise ValueError("Informe telefone apenas com dígitos, ou o identificador de grupo permitido pela Z-API")
        return self._request("POST", "send-text", json={"phone": normalized, "message": message})

    def create_group(self, group_name: str, phones: list[str], *, auto_invite: bool = False) -> dict:
        if not group_name.strip() or not phones:
            raise ValueError("Informe o nome do grupo e pelo menos um participante")
        normalized=[]
        for phone in phones:
            digits=''.join(ch for ch in str(phone) if ch.isdigit())
            if not 10 <= len(digits) <= 15:
                raise ValueError("Telefone de participante inválido")
            if digits not in normalized:
                normalized.append(digits)
        return self._request("POST", "create-group", json={
            "groupName": group_name.strip(), "phones": normalized,
            "autoInvite": bool(auto_invite),
        })

    def status(self) -> dict:
        return self._request("GET", "status")

    def set_received_webhook(self, callback_url: str) -> dict:
        if not callback_url.startswith("https://"):
            raise ValueError("A Z-API aceita somente webhook HTTPS")
        return self._request("PUT", "update-webhook-received", json={"value": callback_url})


    def configure_webhooks(self, callback_url: str) -> dict:
        from urllib.parse import urlparse
        parsed = urlparse(callback_url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Webhook deve usar HTTPS sem credenciais embutidas')
        return self._request('PUT', 'update-every-webhooks', json={'value': callback_url})
