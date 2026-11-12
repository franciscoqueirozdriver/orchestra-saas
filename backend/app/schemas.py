from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


def _validate_https_base(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use uma URL base HTTPS sem usuário ou senha embutidos")
    if parsed.port not in (None, 443) or parsed.query or parsed.fragment:
        raise ValueError("Porta customizada, query ou fragmento não permitidos para a URL do provedor")
    operation=parsed.path.rstrip('/').lower()
    if any(operation.endswith(suffix) for suffix in ('/chat/completions','/responses','/messages','/embeddings',':generatecontent')):
        raise ValueError('Informe a raiz da API, sem o caminho da operação')
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


def _provider_api_origin(value: str) -> str:
    value = value.strip().rstrip('/')
    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Informe a URL Server HTTPS do painel, sem usuário ou senha')
    if parsed.port not in (None, 443) or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('A URL Server deve ser só a origem HTTPS, sem caminho, query ou fragmento')
    return value


class ZapiInstanceCreate(BaseModel):
    provider: str = Field(default='zapi', pattern=r'^(zapi|wame|wame_qr|wame_official)$')
    label: str = Field(min_length=2, max_length=120)
    instance_id: str = Field(min_length=3, max_length=160, pattern=r"^[A-Za-z0-9_-]+$")
    token: str = Field(min_length=4, max_length=512)
    client_token: str | None = Field(default=None, max_length=512)
    api_base_url: str | None = Field(default=None, max_length=500)

    @model_validator(mode='after')
    def normalize_provider_credentials(self):
        if self.provider == 'wame' or self.provider.startswith('wame_'):
            self.client_token = None
            if not self.api_base_url:
                raise ValueError('Cole o Server do painel WAME')
            self.api_base_url = _provider_api_origin(self.api_base_url)
        else:
            self.api_base_url = None
        return self


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

    @field_validator('api_key','embedding_api_key')
    @classmethod
    def normalize_key(cls,value):
        return value.strip() or None if value is not None else None

    @field_validator('model','embedding_model')
    @classmethod
    def normalize_model(cls,value):
        value=value.strip()
        if not value or any(ord(c)<32 for c in value):
            raise ValueError('Informe um identificador de modelo válido')
        return value

    @model_validator(mode='after')
    def normalize_native_model(self):
        from app.llm_client import resolved_protocol
        if resolved_protocol(self.provider,self.protocol)=='gemini' and self.model.startswith('models/'):
            self.model=self.model[len('models/'):]
            if not self.model:raise ValueError('Informe o identificador do modelo Gemini')
        return self


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


class InstancePolicyUpdate(BaseModel):
    agent_id: str | None = None
    sending_enabled: bool | None = None
    messages_per_minute: int | None = Field(default=None, ge=1, le=60)


class InterventionRoutingUpdate(BaseModel):
    group_id: str = Field(min_length=5, max_length=240, pattern=r"^[A-Za-z0-9@._-]+$")
    staff_phones: list[str] = Field(min_length=1, max_length=100)

    @field_validator('staff_phones')
    @classmethod
    def normalize_staff_phones(cls, values):
        normalized=[]
        for value in values:
            digits=''.join(ch for ch in value if ch.isdigit())
            if not 10 <= len(digits) <= 15:
                raise ValueError('Cada atendente deve ter um telefone internacional com 10 a 15 dígitos')
            if digits not in normalized:
                normalized.append(digits)
        if not normalized:
            raise ValueError('Cadastre ao menos um telefone de atendente autorizado')
        return normalized


class InterventionGroupCreate(BaseModel):
    group_name: str = Field(min_length=2,max_length=120)
    phones: list[str] = Field(min_length=1,max_length=100)
    auto_invite: bool = False
    confirmed_not_connected_number: bool
    confirm_auto_invites: bool = False

    @field_validator('phones')
    @classmethod
    def normalize_group_phones(cls, values):
        normalized=[]
        for value in values:
            digits=''.join(ch for ch in value if ch.isdigit())
            if not 10 <= len(digits) <= 15:
                raise ValueError('Cada participante deve ter um telefone internacional com 10 a 15 dígitos')
            if digits not in normalized:
                normalized.append(digits)
        if not normalized:
            raise ValueError('Informe ao menos um participante')
        return normalized

    @model_validator(mode='after')
    def confirm_private_invites(self):
        if self.auto_invite and not self.confirm_auto_invites:
            raise ValueError('Confirme que deseja enviar convites privados para quem não puder ser adicionado diretamente')
        return self


class InterventionGroupConfirmation(BaseModel):
    confirmed_received: bool


class ConversationPolicyUpdate(BaseModel):
    status: str = Field(pattern=r"^(open|human|paused)$")
    consent_status: str = Field(pattern=r"^(unknown|granted|denied)$")
    consent_evidence: str = Field(default="", max_length=1000)


class ConversationConsentUpdate(BaseModel):
    evidence: str = Field(min_length=5, max_length=1000)


class ConversationProfile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool = False
    tone: str = Field(default='neutral', pattern=r'^(neutral|formal|friendly)$')
    conciseness: str = Field(default='balanced', pattern=r'^(short|balanced|detailed)$')
    emojis: str = Field(default='none', pattern=r'^(none|sparing)$')
    vocabulary: list[str] = Field(default_factory=list, max_length=20)
    examples: list[str] = Field(default_factory=list, max_length=8)
    # Business capability is agent-specific; shared language and delivery rules are global.
    visit_booking_enabled: bool = False
    context_minutes: int = Field(default=60, ge=5, le=1440)
    max_wait_seconds: int = Field(default=20, ge=3, le=60)
    part_chars: int = Field(default=1500, ge=300, le=4000)
    part_delay_seconds: int = Field(default=1, ge=0, le=5)
    presence: bool = False
    humanized_delivery: bool = False
    humanized_target_chars: int = Field(default=180, ge=100, le=180)
    humanized_max_chars: int = Field(default=300, ge=180, le=300)
    humanized_max_parts: int = Field(default=3, ge=1, le=3)
    humanized_delay_seconds: int = Field(default=2, ge=1, le=5)
    formality: int = Field(default=3, ge=0, le=10)
    empathy: int = Field(default=7, ge=0, le=10)
    humor: int = Field(default=3, ge=0, le=10)
    objectivity: int = Field(default=7, ge=0, le=10)
    proactivity: int = Field(default=5, ge=0, le=10)
    max_lines: int = Field(default=4, ge=1, le=8)
    forbidden_phrases: list[str] = Field(default_factory=list, max_length=10)
    adaptive_style: bool = True
    memory_enabled: bool = False
    structured_decision_enabled: bool = False
    presence_enabled: bool = False

    @model_validator(mode='after')
    def valid_humanized_sizes(self):
        if self.humanized_target_chars > self.humanized_max_chars:
            raise ValueError('O tamanho-alvo não pode superar o tamanho máximo')
        return self

    @field_validator('vocabulary','examples','forbidden_phrases')
    @classmethod
    def bounded_style(cls, values):
        if any(not v.strip() or len(v)>1000 for v in values):
            raise ValueError('Itens de estilo precisam ter de 1 a 1000 caracteres')
        return [v.strip() for v in values]


class ConversationActionRequest(BaseModel):
    expected_revision: int = Field(ge=0)


class ConversationSendRequest(ConversationActionRequest):
    message: str = Field(min_length=1,max_length=4000)
    idempotency_key: str = Field(min_length=16,max_length=80)


class KnowledgeSearchUpsert(BaseModel):
    connection_id: str | None = Field(default=None,max_length=36)
    base_url: str | None = Field(default=None,max_length=500)
    model: str = Field(min_length=1,max_length=160)
    api_key: str | None = Field(default=None,max_length=1000)

    @field_validator('base_url')
    @classmethod
    def validate_base(cls,value):
        return _validate_https_base(value) if value else None

    @field_validator('model')
    @classmethod
    def validate_model(cls,value):
        value=value.strip()
        if not value or any(ord(c)<32 for c in value):raise ValueError('Informe o modelo de embeddings')
        return value

    @field_validator('api_key')
    @classmethod
    def validate_key(cls,value):
        return value.strip() or None if value is not None else None


class BusinessProfileUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(default='', max_length=160)
    description: str = Field(default='', max_length=2000)
    segment: str = Field(default='', max_length=160)
    regions: list[str] = Field(default_factory=list, max_length=30)
    hours: str = Field(default='', max_length=1000)
    policies: list[str] = Field(default_factory=list, max_length=30)
    contact: str = Field(default='', max_length=300)
    notes: str = Field(default='', max_length=4000)

    @field_validator('regions', 'policies')
    @classmethod
    def bounded_lists(cls, values):
        if any(not v.strip() or len(v) > 500 for v in values):
            raise ValueError('Itens de negócio precisam ter de 1 a 500 caracteres')
        return [v.strip() for v in values]


class BusinessProductWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default='', max_length=2000)
    price_text: str = Field(default='', max_length=200)
    conditions: str = Field(default='', max_length=1000)
    active: bool = True


class BusinessProcessWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default='', max_length=2000)
    steps: list[str] = Field(default_factory=list, max_length=30)
    sla_text: str = Field(default='', max_length=500)
    active: bool = True

    @field_validator('steps')
    @classmethod
    def bounded_steps(cls, values):
        if any(not v.strip() or len(v) > 500 for v in values):
            raise ValueError('Etapas precisam ter de 1 a 500 caracteres')
        return [v.strip() for v in values]
