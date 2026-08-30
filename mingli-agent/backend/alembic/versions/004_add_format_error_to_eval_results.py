"""add format_error to eval_results

Revision ID: 004_format_error
Revises: 003_usage_logs
Create Date: 2026-08-13 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004_format_error'
down_revision = '003_usage_logs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 eval_results 表（如果不存在）
    op.create_table(
        'eval_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dataset_id', sa.String(100), nullable=True, comment='评测集批次ID'),
        sa.Column('total', sa.Integer(), nullable=True, comment='总测试数'),
        sa.Column('passed', sa.Integer(), nullable=True, comment='通过数'),
        sa.Column('failed', sa.Integer(), nullable=True, comment='失败数'),
        sa.Column('pass_rate', sa.Float(), nullable=True, comment='通过率'),
        sa.Column('detail', sa.Text(), nullable=True, comment='详细结果JSON'),
        sa.Column('format_error', sa.Text(), nullable=True, 
                  comment='L2格式完成率错误信息JSON: {"json_parse_failed":bool,"pydantic_validation_failed":bool,"error_detail":str}'),
        sa.Column('format_pass_rate', sa.Float(), nullable=True, 
                  comment='L2格式完成率（通过Pydantic校验的比例）'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_column('eval_results', 'format_pass_rate')
    op.drop_column('eval_results', 'format_error')
