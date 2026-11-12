"""Add tenant business profile, product and process configuration."""
from alembic import op
import sqlalchemy as sa

revision = '0011_business_configuration'
down_revision = '0010_wame_api_base_url'
branch_labels = depends_on = None


def upgrade():
    op.create_table('business_profiles',
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('data', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table('business_products',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(160), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('price_text', sa.String(200), nullable=False, server_default=''),
        sa.Column('conditions', sa.Text(), nullable=False, server_default=''),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('ix_business_products_tenant_active', 'business_products', ['tenant_id', 'active'])
    op.create_table('business_processes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(160), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('steps', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('sla_text', sa.String(500), nullable=False, server_default=''),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('ix_business_processes_tenant_active', 'business_processes', ['tenant_id', 'active'])
    op.add_column('agents', sa.Column('business_override', sa.JSON(), nullable=False, server_default='{}'))


def downgrade():
    op.drop_column('agents', 'business_override')
    op.drop_index('ix_business_processes_tenant_active', table_name='business_processes')
    op.drop_table('business_processes')
    op.drop_index('ix_business_products_tenant_active', table_name='business_products')
    op.drop_table('business_products')
    op.drop_table('business_profiles')
