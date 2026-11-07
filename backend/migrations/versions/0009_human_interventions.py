"""Add organization-configured team intervention routing and claims."""
from alembic import op
import sqlalchemy as sa

revision = '0009_human_interventions'
down_revision = '0008_historical_conversations'
branch_labels = depends_on = None


def upgrade():
    op.add_column('zapi_instances', sa.Column('provider',sa.String(40),nullable=False,server_default='zapi'))
    op.add_column('zapi_instances', sa.Column('intervention_group_id', sa.String(240)))
    op.add_column('zapi_instances', sa.Column('intervention_staff_phones', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('zapi_instances', sa.Column('intervention_group_validation', sa.String(24), nullable=False, server_default='pending'))
    op.add_column('zapi_instances', sa.Column('intervention_group_tested_at', sa.DateTime(timezone=True)))
    op.add_column('zapi_instances', sa.Column('intervention_group_validated_at', sa.DateTime(timezone=True)))
    op.create_table('intervention_requests',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('instance_id', sa.String(36), sa.ForeignKey('zapi_instances.id', ondelete='CASCADE'), nullable=False),
        sa.Column('conversation_id', sa.String(36), nullable=False),
        sa.Column('code', sa.String(8), nullable=False),
        sa.Column('reason', sa.String(80), nullable=False),
        sa.Column('status', sa.String(24), nullable=False, server_default='awaiting_claim'),
        sa.Column('notification_status', sa.String(24), nullable=False, server_default='pending'),
        sa.Column('claimed_by_phone', sa.String(24)),
        sa.Column('context_delivery_status', sa.String(24), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('claimed_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['conversation_id','tenant_id'], ['conversations.id','conversations.tenant_id'], ondelete='CASCADE'))
    op.create_index('ix_intervention_requests_tenant_id', 'intervention_requests', ['tenant_id'])
    op.create_index('ix_intervention_requests_instance_id', 'intervention_requests', ['instance_id'])
    op.create_index('ix_intervention_requests_conversation_id', 'intervention_requests', ['conversation_id'])
    op.create_index('ix_intervention_tenant_status_created', 'intervention_requests', ['tenant_id','status','created_at'])
    op.create_index('uq_intervention_instance_code_open','intervention_requests',['instance_id','code'],unique=True,
        postgresql_where=sa.text("status IN ('awaiting_claim','claimed','setup_required')"),
        sqlite_where=sa.text("status IN ('awaiting_claim','claimed','setup_required')"))


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text('SELECT 1 FROM intervention_requests LIMIT 1')).first():
        raise RuntimeError('Downgrade recusado: preserve os pedidos de intervenção antes de remover seu histórico')
    op.drop_index('uq_intervention_instance_code_open', table_name='intervention_requests')
    op.drop_index('ix_intervention_tenant_status_created', table_name='intervention_requests')
    op.drop_index('ix_intervention_requests_conversation_id', table_name='intervention_requests')
    op.drop_index('ix_intervention_requests_instance_id', table_name='intervention_requests')
    op.drop_index('ix_intervention_requests_tenant_id', table_name='intervention_requests')
    op.drop_table('intervention_requests')
    for name in ('intervention_group_validated_at','intervention_group_tested_at','intervention_group_validation','intervention_staff_phones','intervention_group_id','provider'):
        op.drop_column('zapi_instances', name)
