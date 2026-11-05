from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    outbound_enabled: bool = False
    model_history_limit: int = Field(default=14, ge=2, le=200)
    database_url: str = "postgresql+psycopg://orquestra:orquestra@localhost:5432/orquestra"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = ""
    access_token_minutes: int = Field(default=30, ge=5, le=240)
    credentials_encryption_key: str = ""
    public_base_url: str = ""
    zapi_api_base_url: str = "https://api.z-api.io"
    media_dir: str = "./data/media"
    upload_max_mb: int = Field(default=20, ge=1, le=50)
    embedding_dimensions: int = Field(default=1536)
    llm_request_timeout_seconds: int = Field(default=45, ge=5, le=180)
    message_group_window_seconds: int = Field(default=3, ge=0, le=15)

    @field_validator("public_base_url")
    @classmethod
    def validate_public_base_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value:
            return value
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("PUBLIC_BASE_URL precisa ser uma origem HTTPS válida")
        if parsed.port not in (None, 443) or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ValueError("PUBLIC_BASE_URL deve conter somente origem HTTPS, sem caminho, query ou porta customizada")
        return value

    @field_validator("zapi_api_base_url")
    @classmethod
    def validate_zapi_base_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value.startswith("https://"):
            raise ValueError("A URL base da Z-API precisa usar HTTPS")
        return value

    @field_validator("embedding_dimensions")
    @classmethod
    def validate_embedding_dimensions(cls, value: int) -> int:
        if value != 1536:
            raise ValueError("A versão atual usa 1536 dimensões no pgvector; altere também o schema/migração antes de mudar")
        return value

    def ensure_runtime_secrets(self) -> None:
        if len(self.jwt_secret) < 32:
            raise RuntimeError("JWT_SECRET precisa ter pelo menos 32 caracteres aleatórios")
        try:
            Fernet(self.credentials_encryption_key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise RuntimeError("CREDENTIALS_ENCRYPTION_KEY inválida; gere uma chave Fernet Base64") from exc
        if self.environment.lower() == "production" and not self.public_base_url:
            raise RuntimeError("PUBLIC_BASE_URL HTTPS é obrigatório em produção para webhooks Z-API")
        Path(self.media_dir).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
