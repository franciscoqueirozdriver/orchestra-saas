"""Store the WAME Server URL shown in the provider panel on each connection."""
from alembic import op
import sqlalchemy as sa

revision = '0010_wame_api_base_url'
down_revision = '0009_human_interventions'
branch_labels = depends_on = None


def upgrade():
    op.add_column('zapi_instances', sa.Column('api_base_url', sa.String(500)))


def downgrade():
    op.drop_column('zapi_instances', 'api_base_url')
