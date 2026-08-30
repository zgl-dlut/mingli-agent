"""add ai_usage_logs table and transactions.biz_type

Revision ID: 003_usage_logs
Revises: 91a591685d35
Create Date: 2026-08-11 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_usage_logs'
down_revision = '91a591685d35'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # AI 请求用量记录表（每次首次报告/追问一条）
    op.create_table(
        'ai_usage_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('biz_type', sa.String(20), nullable=False),
        sa.Column('input_chars', sa.Integer(), server_default='0', nullable=False),
        sa.Column('input_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('output_chars', sa.Integer(), server_default='0', nullable=False),
        sa.Column('output_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('cached_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('model', sa.String(100), server_default='', nullable=False),
        sa.Column('success', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('duration_ms', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_usage_logs_user_id', 'ai_usage_logs', ['user_id'])
    op.create_index('idx_usage_logs_created_at', 'ai_usage_logs', ['created_at'])

    # 积分流水业务类型（区分首次报告/追问/充值；历史数据保持 NULL）
    op.add_column('transactions', sa.Column('biz_type', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('transactions', 'biz_type')
    op.drop_index('idx_usage_logs_created_at', table_name='ai_usage_logs')
    op.drop_index('idx_usage_logs_user_id', table_name='ai_usage_logs')
    op.drop_table('ai_usage_logs')
