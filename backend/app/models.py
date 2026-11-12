from datetime import datetime, timezone
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="tenant_admin")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_agent_tenant_name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    llm_config_id: Mapped[str | None] = mapped_column(ForeignKey("llm_configs.id", ondelete="SET NULL"), index=True)
    fallback_config_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    conversation_profile: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    business_override: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_reply_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class BusinessProfile(Base):
    __tablename__ = "business_profiles"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class BusinessProduct(Base):
    __tablename__ = "business_products"
    __table_args__ = (Index("ix_business_products_tenant_active", "tenant_id", "active"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price_text: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    conditions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class BusinessProcess(Base):
    __tablename__ = "business_processes"
    __table_args__ = (Index("ix_business_processes_tenant_active", "tenant_id", "active"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    sla_text: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ZapiInstance(Base):
    __tablename__ = "zapi_instances"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default='zapi', server_default='zapi')
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    instance_id: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), index=True)
    sending_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    messages_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    intervention_group_id: Mapped[str | None] = mapped_column(String(240))
    intervention_staff_phones: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    intervention_group_validation: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default="pending")
    intervention_group_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    intervention_group_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    api_base_url: Mapped[str | None] = mapped_column(String(500))
    token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    client_token_encrypted: Mapped[str | None] = mapped_column(Text)
    callback_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    callback_token_encrypted: Mapped[str | None] = mapped_column(Text)
    callback_previous_hash: Mapped[str | None] = mapped_column(String(64))
    callback_previous_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_checked")
    webhook_configured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class LLMConfig(Base):
    __tablename__ = "llm_configs"
    __table_args__ = (Index("uq_llm_default_tenant", "tenant_id", unique=True, postgresql_where=text("is_default")),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="Principal", server_default="Principal")
    protocol: Mapped[str] = mapped_column(String(40), nullable=False, default="auto", server_default="auto")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=2048, server_default="2048")
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_category: Mapped[str | None] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="openai-compatible")
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(160), nullable=False, default="text-embedding-3-small")
    embedding_base_url: Mapped[str | None] = mapped_column(String(500))
    embedding_api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("tenant_id", "instance_id", "contact_key", name="uq_conversation_contact"), UniqueConstraint("id","tenant_id",name="uq_conversation_id_tenant"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(ForeignKey("zapi_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_key: Mapped[str] = mapped_column(String(180), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    opted_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    consent_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown", server_default="unknown")
    consent_evidence: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    last_incoming_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    turn_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    context_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    context_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pause_reason: Mapped[str | None] = mapped_column(String(40))
    history_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    response_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class HistoricalImportBatch(Base):
    __tablename__ = "historical_import_batches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_sha256", name="uq_history_import_tenant_source"),
        UniqueConstraint("id", "tenant_id", name="uq_history_import_id_tenant"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source_timezone: Mapped[str] = mapped_column(String(80), nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ConversationContactAlias(Base):
    __tablename__ = "conversation_contact_aliases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "instance_id", "contact_key", name="uq_contact_alias_instance_key"),
        ForeignKeyConstraint(["conversation_id", "tenant_id"], ["conversations.id", "conversations.tenant_id"], ondelete="CASCADE"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(ForeignKey("zapi_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    contact_key: Mapped[str] = mapped_column(String(180), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_message_tenant_conversation_created", "tenant_id", "conversation_id", "created_at"),
        ForeignKeyConstraint(["history_import_batch_id", "tenant_id"], ["historical_import_batches.id", "historical_import_batches.tenant_id"], ondelete="CASCADE"),
        UniqueConstraint("history_import_batch_id", "history_source_ordinal", name="uq_history_source_message_ordinal"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    author_kind: Mapped[str] = mapped_column(String(16), nullable=False, default='legacy', server_default='legacy')
    author_name: Mapped[str | None] = mapped_column(Text)
    operator_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    history_import_batch_id: Mapped[str | None] = mapped_column(String(36))
    history_source_ordinal: Mapped[int | None] = mapped_column(Integer)
    original_timestamp_text: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String(180), index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="text")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("instance_id", "event_key", "event_type", name="uq_webhook_event_dedup"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(ForeignKey("zapi_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    event_key: Mapped[str] = mapped_column(String(220), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_error: Mapped[str | None] = mapped_column(String(500))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class KnowledgeSearchConfig(Base):
    __tablename__ = "knowledge_search_configs"
    connection_id: Mapped[str | None] = mapped_column(ForeignKey("llm_configs.id", ondelete="RESTRICT"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    embedding_base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(160), nullable=False)
    embedding_api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(String(240), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False, default="text/plain")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="indexed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (Index("ix_knowledge_chunks_tenant_doc", "tenant_id", "document_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(160), nullable=False)


class MemoryItem(Base):
    __tablename__ = "memory_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="operator")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_outbox_id_tenant"),
        UniqueConstraint("idempotency_key", name="uq_outbox_idempotency_key"),
        UniqueConstraint("tenant_id", "conversation_id", "response_revision", name="uq_outbox_conversation_revision"),
        Index("ix_outbox_tenant_status_created", "tenant_id", "status", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(ForeignKey("zapi_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    response_revision: Mapped[int | None] = mapped_column(Integer)
    delivery_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    author_kind: Mapped[str] = mapped_column(String(16), nullable=False, default='assistant', server_default='assistant')
    operator_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    destination: Mapped[str] = mapped_column(String(180), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_message_id: Mapped[str | None] = mapped_column(String(180))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ModelRun(Base):
    __tablename__ = "model_runs"
    __table_args__ = (UniqueConstraint("tenant_id", "conversation_id", "revision", name="uq_model_run_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"))
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    context_snapshot_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    response_encrypted: Mapped[str | None] = mapped_column(Text)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    selected_config_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConversationTurn(Base):
    __tablename__ = 'conversation_turns'
    __table_args__ = (UniqueConstraint('tenant_id','conversation_id','revision',name='uq_turn_revision'), ForeignKeyConstraint(['conversation_id','tenant_id'],['conversations.id','conversations.tenant_id'],ondelete='CASCADE'))
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey('conversations.id',ondelete='CASCADE'),nullable=False,index=True)
    revision: Mapped[int] = mapped_column(Integer,nullable=False)
    message_ids: Mapped[list] = mapped_column(JSON,nullable=False)
    state: Mapped[dict] = mapped_column(JSON,nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())


class ConversationAction(Base):
    __tablename__ = 'conversation_actions'
    __table_args__ = (ForeignKeyConstraint(['conversation_id','tenant_id'],['conversations.id','conversations.tenant_id'],ondelete='CASCADE'),)
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey('conversations.id',ondelete='CASCADE'),nullable=False,index=True)
    operator_id: Mapped[str | None] = mapped_column(ForeignKey('users.id',ondelete='SET NULL'))
    action: Mapped[str] = mapped_column(String(40),nullable=False)
    revision: Mapped[int] = mapped_column(Integer,nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())


class InterventionRequest(Base):
    __tablename__ = 'intervention_requests'
    __table_args__ = (
        ForeignKeyConstraint(['conversation_id','tenant_id'],['conversations.id','conversations.tenant_id'],ondelete='CASCADE'),
        Index('ix_intervention_tenant_status_created','tenant_id','status','created_at'),
        Index('uq_intervention_instance_code_open','instance_id','code',unique=True,
              postgresql_where=text("status IN ('awaiting_claim','claimed','setup_required')"),
              sqlite_where=text("status IN ('awaiting_claim','claimed','setup_required')")),
    )
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    instance_id: Mapped[str] = mapped_column(ForeignKey('zapi_instances.id',ondelete='CASCADE'),nullable=False,index=True)
    conversation_id: Mapped[str] = mapped_column(String(36),nullable=False,index=True)
    code: Mapped[str] = mapped_column(String(8),nullable=False)
    reason: Mapped[str] = mapped_column(String(80),nullable=False)
    status: Mapped[str] = mapped_column(String(24),nullable=False,default='awaiting_claim',server_default='awaiting_claim')
    notification_status: Mapped[str] = mapped_column(String(24),nullable=False,default='pending',server_default='pending')
    claimed_by_phone: Mapped[str | None] = mapped_column(String(24))
    context_delivery_status: Mapped[str] = mapped_column(String(24),nullable=False,default='pending',server_default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutboxPart(Base):
    __tablename__ = 'outbox_parts'
    __table_args__ = (
        UniqueConstraint('tenant_id','outbox_id','ordinal',name='uq_outbox_part_ordinal'),
        ForeignKeyConstraint(['outbox_id','tenant_id'],['outbox_messages.id','outbox_messages.tenant_id'],ondelete='CASCADE'),
    )
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36),nullable=False,index=True)
    outbox_id: Mapped[str] = mapped_column(String(36),nullable=False,index=True)
    ordinal: Mapped[int] = mapped_column(Integer,nullable=False)
    content: Mapped[str] = mapped_column(Text,nullable=False)
    status: Mapped[str] = mapped_column(String(32),nullable=False,default='pending')
    external_message_id: Mapped[str | None] = mapped_column(String(180),index=True)
    attempts: Mapped[int] = mapped_column(Integer,nullable=False,default=0,server_default='0')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
