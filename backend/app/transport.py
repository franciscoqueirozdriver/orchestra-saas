"""Messaging boundary. No automatic failover after an uncertain external effect."""
from dataclasses import dataclass
from app.security import decrypt_secret
from app.wame_client import WameClient, WameError
from app.zapi_client import ZapiClient, ZapiError

class TransportError(RuntimeError):
    def __init__(self,status_code):
        self.status_code=status_code
        super().__init__('Falha no transporte de mensagens')


@dataclass(frozen=True)
class Receipt:
    message_id: str | None


class ZapiTransport:
    def __init__(self, instance):
        self.client=ZapiClient(instance.instance_id,decrypt_secret(instance.token_encrypted) or '',decrypt_secret(instance.client_token_encrypted))

    def send_text(self, destination, content):
        try:
            remote=self.client.send_text(destination,content)
        except ZapiError as exc:
            raise TransportError(exc.status_code) from None
        identifier=remote.get('messageId') or remote.get('id') or remote.get('zaapId')
        return Receipt(_receipt_id(identifier))

    def composing(self, destination):
        # Presence deliberately unavailable until its contract is homologated.
        return False


class WameTransport:
    def __init__(self, instance):
        self.client = WameClient(decrypt_secret(instance.token_encrypted) or '')

    def send_text(self, destination, content):
        try:
            remote = self.client.send_text(destination, content)
        except WameError as exc:
            raise TransportError(exc.status_code) from None
        return Receipt(_receipt_id(remote.get('messageId')))

    def composing(self, destination):
        return False


def _receipt_id(identifier):
    valid = isinstance(identifier, str) and 0 < len(identifier) <= 180 and identifier == identifier.strip() and identifier.isprintable()
    return identifier if valid else None


def is_wame_provider(provider) -> bool:
    return isinstance(provider, str) and (provider == 'wame' or provider.startswith('wame_'))


def client_for(instance):
    if is_wame_provider(getattr(instance, 'provider', 'zapi')):
        return WameClient(decrypt_secret(instance.token_encrypted) or '')
    return ZapiClient(instance.instance_id, decrypt_secret(instance.token_encrypted) or '', decrypt_secret(instance.client_token_encrypted))


def for_instance(instance):
    if is_wame_provider(getattr(instance, 'provider', 'zapi')):
        return WameTransport(instance)
    return ZapiTransport(instance)
