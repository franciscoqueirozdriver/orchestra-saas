"""One immutable model context per conversation revision. No data deletion."""
from alembic import op
import sqlalchemy as sa

revision = '0004_model_run_uniqueness'
down_revision = '0003_model_routing'
branch_labels = depends_on = None


def upgrade():
    duplicates = op.get_bind().execute(sa.text(
        'SELECT 1 FROM model_runs WHERE conversation_id IS NOT NULL '
        'GROUP BY tenant_id, conversation_id, revision HAVING count(*) > 1 LIMIT 1'
    )).first()
    if duplicates:
        raise RuntimeError('Revisão duplicada em model_runs: revisar dados antes da migração; nenhum registro foi removido')
    op.add_column('zapi_instances', sa.Column('callback_token_encrypted', sa.Text()))
    op.add_column('zapi_instances', sa.Column('callback_previous_hash', sa.String(64)))
    op.add_column('zapi_instances', sa.Column('callback_previous_until', sa.DateTime(timezone=True)))
    op.create_unique_constraint('uq_model_run_revision', 'model_runs', ['tenant_id', 'conversation_id', 'revision'])


def downgrade():
    if op.get_bind().execute(sa.text('SELECT 1 FROM llm_configs GROUP BY tenant_id HAVING count(*) > 1 LIMIT 1')).first():
        raise RuntimeError('Downgrade recusado: reconcilie conexões antes de reverter a cadeia')
    for name in ('callback_previous_until', 'callback_previous_hash', 'callback_token_encrypted'):
        op.drop_column('zapi_instances', name)
    op.drop_constraint('uq_model_run_revision', 'model_runs', type_='unique')
