"""add content_unlocks table for deep-reading unlock state

Revision ID: 010_content_unlocks
Revises: 009_eval_detail_mt
Create Date: 2026-10-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '010_content_unlocks'
down_revision = '009_eval_detail_mt'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'content_unlocks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='用户ID'),
        sa.Column('message_id', sa.Integer(), nullable=False, comment='大纲消息ID'),
        sa.Column('unlock_type', sa.String(20), nullable=False, server_default='points', comment='解锁方式'),
        sa.Column('points_cost', sa.Integer(), nullable=False, server_default='0', comment='解锁消耗积分'),
        sa.Column('unlocked_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'message_id', name='uq_content_unlock_user_message'),
    )
    op.create_index('ix_content_unlocks_user_id', 'content_unlocks', ['user_id'])
    op.create_index('ix_content_unlocks_message_id', 'content_unlocks', ['message_id'])


def downgrade() -> None:
    op.drop_index('ix_content_unlocks_message_id', table_name='content_unlocks')
    op.drop_index('ix_content_unlocks_user_id', table_name='content_unlocks')
    op.drop_table('content_unlocks')
