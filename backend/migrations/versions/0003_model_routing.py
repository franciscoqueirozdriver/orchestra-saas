"""Provider-neutral connections and context-preserving fallback."""
from alembic import op
import sqlalchemy as sa
revision = "0003_model_routing"
down_revision = "0002_delivery_controls"
branch_labels = depends_on = None

def upgrade():
    # SQLAlchemy originally generated a unique index, not a named table constraint.
    op.drop_index("ix_llm_configs_tenant_id", table_name="llm_configs")
    op.create_index("ix_llm_configs_tenant_id", "llm_configs", ["tenant_id"])
    for column in [
        sa.Column("name",sa.String(120),nullable=False,server_default="Principal"),
        sa.Column("protocol",sa.String(40),nullable=False,server_default="auto"),
        sa.Column("enabled",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("is_default",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column("max_output_tokens",sa.Integer(),nullable=False,server_default="2048"),
        sa.Column("cooldown_until",sa.DateTime(timezone=True)),
        sa.Column("last_error_category",sa.String(40))]: op.add_column("llm_configs",column)
    op.execute("UPDATE llm_configs SET is_default=true")
    op.create_index("uq_llm_default_tenant", "llm_configs", ["tenant_id"], unique=True, postgresql_where=sa.text("is_default"))
    op.add_column("agents",sa.Column("llm_config_id",sa.String(36),sa.ForeignKey("llm_configs.id",ondelete="SET NULL")))
    op.create_index("ix_agents_llm_config_id","agents",["llm_config_id"])
    op.add_column("agents",sa.Column("fallback_config_ids",sa.JSON(),nullable=False,server_default="[]"))
    op.create_table("model_runs",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("tenant_id",sa.String(36),sa.ForeignKey("tenants.id",ondelete="CASCADE"),nullable=False),
        sa.Column("conversation_id",sa.String(36),sa.ForeignKey("conversations.id",ondelete="CASCADE")),
        sa.Column("agent_id",sa.String(36),sa.ForeignKey("agents.id",ondelete="SET NULL")),
        sa.Column("revision",sa.Integer(),nullable=False),
        sa.Column("context_snapshot_encrypted",sa.Text(),nullable=False),
        sa.Column("response_encrypted",sa.Text()),
        sa.Column("context_hash",sa.String(64),nullable=False),
        sa.Column("attempts",sa.JSON(),nullable=False),
        sa.Column("selected_config_id",sa.String(36)),
        sa.Column("status",sa.String(32),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_index("ix_model_runs_tenant_id","model_runs",["tenant_id"])
    op.create_index("ix_model_runs_conversation_id","model_runs",["conversation_id"])

def downgrade():
    op.drop_table("model_runs")
    op.drop_index("ix_agents_llm_config_id",table_name="agents")
    op.drop_column("agents","fallback_config_ids")
    op.drop_column("agents","llm_config_id")
    op.drop_index("uq_llm_default_tenant",table_name="llm_configs")
    for column in ["last_error_category","cooldown_until","max_output_tokens","is_default","enabled","protocol","name"]: op.drop_column("llm_configs",column)
    # Deliberately refuse to discard additional connections on downgrade.
    op.drop_index("ix_llm_configs_tenant_id",table_name="llm_configs")
    op.create_index("ix_llm_configs_tenant_id","llm_configs",["tenant_id"],unique=True)
