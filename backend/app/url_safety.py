import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeExternalURL(ValueError):
    pass


def validate_public_https(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeExternalURL("URL externa deve ser HTTPS e não pode conter credenciais")
    if parsed.port not in (None, 443) or parsed.query or parsed.fragment:
        raise UnsafeExternalURL("Porta, query ou fragmento não permitido na URL externa")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal")):
        raise UnsafeExternalURL("Host local/interno não permitido")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise UnsafeExternalURL("Não foi possível resolver o host externo") from exc
    if not addresses:
        raise UnsafeExternalURL("Host externo sem endereços resolvidos")
    for address in addresses:
        try:
            if not ipaddress.ip_address(address).is_global:
                raise UnsafeExternalURL("Host externo resolve para endereço não público")
        except ValueError as exc:
            raise UnsafeExternalURL("Endereço de rede inválido") from exc
