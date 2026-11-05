"""Opt-in conversational core, private provenance and durable reply parts."""
from alembic import op
import sqlalchemy as sa

revision = '0005_conversation_core'
down_revision = '0004_model_run_uniqueness'
branch_labels = depends_on = None


def upgrade():
    op.add_column('outbox_messages',sa.Column('delivery_config',sa.JSON(),nullable=False,server_default='{}'))
    op.add_column('agents',sa.Column('conversation_profile',sa.JSON(),nullable=False,server_default='{}'))
    for column in [sa.Column('turn_started_at',sa.DateTime(timezone=True)),sa.Column('context_state',sa.JSON(),nullable=False,server_default='{}'),sa.Column('context_expires_at',sa.DateTime(timezone=True)),sa.Column('pause_reason',sa.String(40))]:
        op.add_column('conversations',column)
    op.add_column('memory_items',sa.Column('approved',sa.Boolean(),nullable=False,server_default='false'))
    for table,default in [('messages','legacy'),('outbox_messages','assistant')]:
        op.add_column(table,sa.Column('author_kind',sa.String(16),nullable=False,server_default=default))
        op.add_column(table,sa.Column('operator_id',sa.String(36),sa.ForeignKey('users.id',ondelete='SET NULL')))
    op.create_unique_constraint('uq_conversation_id_tenant','conversations',['id','tenant_id'])
    op.create_unique_constraint('uq_outbox_id_tenant','outbox_messages',['id','tenant_id'])
    op.create_table('conversation_turns',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('tenant_id',sa.String(36),sa.ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False),
        sa.Column('conversation_id',sa.String(36),sa.ForeignKey('conversations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),sa.Column('message_ids',sa.JSON(),nullable=False),sa.Column('state',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id','conversation_id','revision',name='uq_turn_revision'),
        sa.ForeignKeyConstraint(['conversation_id','tenant_id'],['conversations.id','conversations.tenant_id'],ondelete='CASCADE'))
    op.create_table('conversation_actions',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('tenant_id',sa.String(36),sa.ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False),
        sa.Column('conversation_id',sa.String(36),sa.ForeignKey('conversations.id',ondelete='CASCADE'),nullable=False),
        sa.Column('operator_id',sa.String(36),sa.ForeignKey('users.id',ondelete='SET NULL')),
        sa.Column('action',sa.String(40),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['conversation_id','tenant_id'],['conversations.id','conversations.tenant_id'],ondelete='CASCADE'))
    op.create_table('outbox_parts',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('tenant_id',sa.String(36),nullable=False),sa.Column('outbox_id',sa.String(36),nullable=False),
        sa.Column('ordinal',sa.Integer(),nullable=False),sa.Column('content',sa.Text(),nullable=False),sa.Column('status',sa.String(32),nullable=False),
        sa.Column('external_message_id',sa.String(180)),sa.Column('attempts',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id','outbox_id','ordinal',name='uq_outbox_part_ordinal'),
        sa.ForeignKeyConstraint(['outbox_id','tenant_id'],['outbox_messages.id','outbox_messages.tenant_id'],ondelete='CASCADE'))
    for table,columns in [('conversation_turns',['tenant_id','conversation_id']),('conversation_actions',['tenant_id','conversation_id']),('outbox_parts',['tenant_id','outbox_id','external_message_id'])]:
        for column in columns:op.create_index(f'ix_{table}_{column}',table,[column])


def downgrade():
    bind=op.get_bind()
    # Refuse data loss; old code cannot safely understand a multipart delivery.
    if bind.execute(sa.text('SELECT 1 FROM outbox_parts LIMIT 1')).first() or bind.execute(sa.text('SELECT 1 FROM conversation_turns LIMIT 1')).first() or bind.execute(sa.text('SELECT 1 FROM conversation_actions LIMIT 1')).first():
        raise RuntimeError('Downgrade recusado: preserve e reconcilie dados do núcleo antes de remover schema')
    if bind.execute(sa.text("SELECT 1 FROM agents WHERE conversation_profile::jsonb <> '{}'::jsonb LIMIT 1")).first() or bind.execute(sa.text('SELECT 1 FROM memory_items WHERE approved LIMIT 1')).first():
        raise RuntimeError('Downgrade recusado: preserve perfis e aprovações antes de remover schema')
    if bind.execute(sa.text('SELECT 1 FROM llm_configs GROUP BY tenant_id HAVING count(*)>1 LIMIT 1')).first():
        raise RuntimeError('Downgrade recusado: reconcilie conexões antes de reverter a cadeia')
    for table in ('outbox_parts','conversation_actions','conversation_turns'):op.drop_table(table)
    op.drop_constraint('uq_outbox_id_tenant','outbox_messages',type_='unique')
    op.drop_constraint('uq_conversation_id_tenant','conversations',type_='unique')
    for table in ('messages','outbox_messages'):
        op.drop_column(table,'operator_id');op.drop_column(table,'author_kind')
    op.drop_column('memory_items','approved')
    for name in ('pause_reason','context_expires_at','context_state','turn_started_at'):op.drop_column('conversations',name)
    op.drop_column('outbox_messages','delivery_config')
    op.drop_column('agents','conversation_profile')
