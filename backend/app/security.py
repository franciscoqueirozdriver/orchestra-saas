from datetime import datetime, timedelta, timezone
import hashlib

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

_password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("A senha precisa ter pelo menos 12 caracteres")
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def _fernet() -> Fernet:
    try:
        return Fernet(settings.credentials_encryption_key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise RuntimeError("CREDENTIALS_ENCRYPTION_KEY inválida; gere uma chave Fernet Base64") from exc


def encrypt_secret(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError) as exc:
        raise RuntimeError("Não foi possível descriptografar a credencial; a chave atual precisa ser a mesma usada ao gravá-la") from exc


def hash_callback_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def callback_secret_matches(expected_hash: str, supplied: str) -> bool:
    import hmac
    return hmac.compare_digest(expected_hash, hash_callback_secret(supplied))
