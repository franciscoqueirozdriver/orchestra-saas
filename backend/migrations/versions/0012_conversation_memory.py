"""Add conversation memory provenance fields."""
from alembic import op
import sqlalchemy as sa

revision = '0012_conversation_memory'
down_revision = '0011_business_configuration'
branch_labels = depends_on = None


def upgrade():
    op.add_column('memory_items', sa.Column('kind', sa.String(24), nullable=False, server_default='note'))
    op.add_column('memory_items', sa.Column('fact_key', sa.String(120)))
    op.add_column('memory_items', sa.Column('source_message_id', sa.String(220)))
    op.add_column('memory_items', sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'))
    op.add_column('memory_items', sa.Column('last_seen_at', sa.DateTime(timezone=True)))
    op.create_index('ix_memory_tenant_contact_kind', 'memory_items', ['tenant_id', 'contact_key', 'kind'])


def downgrade():
    op.drop_index('ix_memory_tenant_contact_kind', table_name='memory_items')
    op.drop_column('memory_items', 'last_seen_at')
    op.drop_column('memory_items', 'confidence')
    op.drop_column('memory_items', 'source_message_id')
    op.drop_column('memory_items', 'fact_key')
    op.drop_column('memory_items', 'kind')
