"""Persist imported WhatsApp history in tenant conversations with provenance."""
from alembic import op
import sqlalchemy as sa

revision = '0008_historical_conversations'
down_revision = '0007_search_connection'
branch_labels = depends_on = None


def upgrade():
    op.add_column('conversations', sa.Column('history_only', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table('historical_import_batches',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_sha256', sa.String(64), nullable=False),
        sa.Column('source_version', sa.String(80), nullable=False),
        sa.Column('source_timezone', sa.String(80), nullable=False),
        sa.Column('message_count', sa.Integer(), nullable=False),
        sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'source_sha256', name='uq_history_import_tenant_source'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_history_import_id_tenant'))
    op.create_index('ix_historical_import_batches_tenant_id', 'historical_import_batches', ['tenant_id'])

    op.create_table('conversation_contact_aliases',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('instance_id', sa.String(36), sa.ForeignKey('zapi_instances.id', ondelete='CASCADE'), nullable=False),
        sa.Column('conversation_id', sa.String(36), nullable=False),
        sa.Column('contact_key', sa.String(180), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'instance_id', 'contact_key', name='uq_contact_alias_instance_key'),
        sa.ForeignKeyConstraint(['conversation_id', 'tenant_id'], ['conversations.id', 'conversations.tenant_id'], ondelete='CASCADE'))
    for name, column in [('ix_conversation_contact_aliases_tenant_id','tenant_id'),
                         ('ix_conversation_contact_aliases_instance_id','instance_id'),
                         ('ix_conversation_contact_aliases_conversation_id','conversation_id')]:
        op.create_index(name, 'conversation_contact_aliases', [column])

    op.add_column('messages', sa.Column('author_name', sa.Text()))
    op.add_column('messages', sa.Column('history_import_batch_id', sa.String(36)))
    op.add_column('messages', sa.Column('history_source_ordinal', sa.Integer()))
    op.add_column('messages', sa.Column('original_timestamp_text', sa.Text()))
    op.create_foreign_key('fk_message_history_batch_tenant', 'messages', 'historical_import_batches',
        ['history_import_batch_id', 'tenant_id'], ['id', 'tenant_id'], ondelete='CASCADE')
    op.create_unique_constraint('uq_history_source_message_ordinal', 'messages',
        ['history_import_batch_id', 'history_source_ordinal'])


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text('SELECT 1 FROM historical_import_batches LIMIT 1')).first():
        raise RuntimeError('Downgrade recusado: preserve o histórico importado antes de remover sua proveniência')
    if bind.execute(sa.text('SELECT 1 FROM conversation_contact_aliases LIMIT 1')).first():
        raise RuntimeError('Downgrade recusado: preserve os vínculos de contato antes de remover os aliases')
    op.drop_constraint('uq_history_source_message_ordinal', 'messages', type_='unique')
    op.drop_constraint('fk_message_history_batch_tenant', 'messages', type_='foreignkey')
    for column in ('original_timestamp_text', 'history_source_ordinal', 'history_import_batch_id', 'author_name'):
        op.drop_column('messages', column)
    op.drop_table('conversation_contact_aliases')
    op.drop_index('ix_historical_import_batches_tenant_id', table_name='historical_import_batches')
    op.drop_table('historical_import_batches')
    op.drop_column('conversations', 'history_only')
