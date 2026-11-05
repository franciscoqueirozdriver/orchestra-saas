from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _validate_https_base(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use uma URL base HTTPS sem usuário ou senha embutidos")
    if parsed.port not in (None, 443) or parsed.query or parsed.fragment:
        raise ValueError("Porta customizada, query ou fragmento não permitidos para a URL do provedor")
    return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    tenant_name: str | None = None
    tenant_id: str | None = None


class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    owner_name: str = Field(min_length=2, max_length=160)
    owner_email: EmailStr
    owner_password: str = Field(min_length=12, max_length=256)


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)
    system_prompt: str = Field(default="", max_length=12000)
    enabled: bool = True
    auto_reply_enabled: bool = False
    llm_config_id: str | None = None
    fallback_config_ids: list[str] = Field(default_factory=list, max_length=8)


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    system_prompt: str | None = Field(default=None, max_length=12000)
    enabled: bool | None = None
    auto_reply_enabled: bool | None = None
    llm_config_id: str | None = None
    fallback_config_ids: list[str] | None = Field(default=None, max_length=8)


class ZapiInstanceCreate(BaseModel):
    label: str = Field(min_length=2, max_length=120)
    instance_id: str = Field(min_length=3, max_length=160, pattern=r"^[A-Za-z0-9_-]+$")
    token: str = Field(min_length=4, max_length=512)
    client_token: str | None = Field(default=None, max_length=512)


class LLMConfigUpsert(BaseModel):
    provider: str = Field(min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9_.-]+$")
    name: str = Field(default="Principal", min_length=1, max_length=120)
    protocol: str = Field(default="auto", pattern=r"^(auto|chat-completions|responses|anthropic|gemini)$")
    enabled: bool = True
    max_output_tokens: int = Field(default=2048, ge=128, le=32768)
    base_url: str = Field(min_length=8, max_length=500)
    model: str = Field(min_length=1, max_length=160)
    embedding_model: str = Field(default="text-embedding-3-small", min_length=1, max_length=160)
    embedding_base_url: str | None = Field(default=None, max_length=500)
    embedding_api_key: str | None = Field(default=None, max_length=1000)
    api_key: str | None = Field(default=None, max_length=1000)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        return _validate_https_base(value)

    @field_validator("embedding_base_url")
    @classmethod
    def validate_embedding_base_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return _validate_https_base(value)


class SendTextRequest(BaseModel):
    phone: str = Field(min_length=5, max_length=80)
    message: str = Field(min_length=1, max_length=4000)
    idempotency_key: str | None = Field(default=None, min_length=16, max_length=80)


class MemoryCreate(BaseModel):
    contact_key: str = Field(min_length=3, max_length=180)
    content: str = Field(min_length=1, max_length=3000)
    expires_at: str | None = None


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    system_prompt: str
    enabled: bool
    auto_reply_enabled: bool
