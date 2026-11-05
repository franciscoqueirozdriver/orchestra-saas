"""Reliable messaging, consent and explicit routing."""
from alembic import op
import sqlalchemy as sa
revision = "0002_delivery_controls"
down_revision = "0001_initial"
branch_labels = depends_on = None

def upgrade():
    op.add_column("zapi_instances", sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id", ondelete="SET NULL")))
    op.create_index("ix_zapi_instances_agent_id", "zapi_instances", ["agent_id"])
    op.add_column("zapi_instances", sa.Column("sending_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("zapi_instances", sa.Column("messages_per_minute", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("conversations", sa.Column("opted_out", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("conversations", sa.Column("consent_status", sa.String(16), nullable=False, server_default="unknown"))
    op.add_column("conversations", sa.Column("consent_evidence", sa.Text(), nullable=False, server_default=""))
    op.add_column("conversations", sa.Column("last_incoming_at", sa.DateTime(timezone=True)))
    op.add_column("conversations", sa.Column("response_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.execute("UPDATE conversations SET last_incoming_at = (SELECT max(created_at) FROM messages WHERE messages.conversation_id = conversations.id AND direction = 'incoming')")
    op.add_column("webhook_events", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("webhook_events", sa.Column("last_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("outbox_messages", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))

def downgrade():
    op.drop_column("outbox_messages", "next_attempt_at")
    for column in ["last_attempt_at", "attempts"]: op.drop_column("webhook_events", column)
    for column in ["response_attempts", "last_incoming_at", "consent_evidence", "consent_status", "opted_out"]: op.drop_column("conversations", column)
    op.drop_index("ix_zapi_instances_agent_id", table_name="zapi_instances")
    for column in ["messages_per_minute", "sending_enabled", "agent_id"]: op.drop_column("zapi_instances", column)
