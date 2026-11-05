"""Separate saved document text and search credentials from conversation models."""
from alembic import op
import sqlalchemy as sa

revision = '0006_knowledge_storage'
down_revision = '0005_conversation_core'
branch_labels = depends_on = None


def upgrade():
    op.add_column('knowledge_documents', sa.Column('extracted_text', sa.Text()))
    op.create_table('knowledge_search_configs',
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('embedding_base_url', sa.String(500), nullable=False),
        sa.Column('embedding_model', sa.String(160), nullable=False),
        sa.Column('embedding_api_key_encrypted', sa.Text(), nullable=False))


def downgrade():
    connection=op.get_bind()
    if connection.execute(sa.text('SELECT 1 FROM knowledge_search_configs LIMIT 1')).first() or connection.execute(sa.text('SELECT 1 FROM knowledge_documents WHERE extracted_text IS NOT NULL LIMIT 1')).first():
        raise RuntimeError('Downgrade recusado: preserve documentos e configuração de busca antes de remover o armazenamento')
    op.drop_table('knowledge_search_configs')
    op.drop_column('knowledge_documents', 'extracted_text')
