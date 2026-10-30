import pytest

from app.security import create_access_token, decode_access_token, decrypt_secret, encrypt_secret, hash_password, verify_password


def test_password_hash_and_verify():
    hashed = hash_password("Senha-forte-de-teste-2026")
    assert hashed != "Senha-forte-de-teste-2026"
    assert verify_password(hashed, "Senha-forte-de-teste-2026")
    assert not verify_password(hashed, "senha-errada")


def test_password_minimum_length():
    with pytest.raises(ValueError):
        hash_password("curta")


def test_jwt_round_trip():
    token = create_access_token("user-123")
    assert decode_access_token(token)["sub"] == "user-123"


def test_credential_encryption_round_trip():
    ciphertext = encrypt_secret("credential-very-secret")
    assert ciphertext != "credential-very-secret"
    assert decrypt_secret(ciphertext) == "credential-very-secret"
    assert encrypt_secret("") is None
