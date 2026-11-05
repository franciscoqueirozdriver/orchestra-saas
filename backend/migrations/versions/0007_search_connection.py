"""Reference an existing tenant connection instead of copying its credential."""
from alembic import op
import sqlalchemy as sa

revision = '0007_search_connection'
down_revision = '0006_knowledge_storage'
branch_labels = depends_on = None


def upgrade():
    op.add_column('knowledge_search_configs', sa.Column('connection_id', sa.String(36)))
    op.create_foreign_key('fk_search_connection', 'knowledge_search_configs', 'llm_configs', ['connection_id'], ['id'], ondelete='RESTRICT')


def downgrade():
    if op.get_bind().execute(sa.text('SELECT 1 FROM knowledge_search_configs WHERE connection_id IS NOT NULL LIMIT 1')).first():
        raise RuntimeError('Downgrade recusado: preserve os vínculos da busca antes de remover a referência')
    op.drop_constraint('fk_search_connection', 'knowledge_search_configs', type_='foreignkey')
    op.drop_column('knowledge_search_configs', 'connection_id')
