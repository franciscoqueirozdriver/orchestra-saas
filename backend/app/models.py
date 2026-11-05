from datetime import datetime, timezone
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
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
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_reply_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ZapiInstance(Base):
    __tablename__ = "zapi_instances"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    instance_id: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), index=True)
    sending_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    messages_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    client_token_encrypted: Mapped[str | None] = mapped_column(Text)
    callback_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_checked")
    webhook_configured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class LLMConfig(Base):
    __tablename__ = "llm_configs"
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
    __table_args__ = (UniqueConstraint("tenant_id", "instance_id", "contact_key", name="uq_conversation_contact"),)
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
    response_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_message_tenant_conversation_created", "tenant_id", "conversation_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
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


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
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
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="operator")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"
    __table_args__ = (
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
