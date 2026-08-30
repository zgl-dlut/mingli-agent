"""add prompt_reviews and prompt_versions tables

Revision ID: 007_prompt_review
Revises: 006_eval_metrics
Create Date: 2026-08-14 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '007_prompt_review'
down_revision = '006_eval_metrics'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 prompt_reviews 表
    op.create_table(
        'prompt_reviews',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('eval_result_id', sa.Integer(), nullable=True, comment='关联的评测结果 ID'),
        sa.Column('badcase_id', sa.Integer(), nullable=True, comment='关联的 badcase ID'),
        sa.Column('report_data', sa.Text(), nullable=True, comment='报告 JSON'),
        sa.Column('user_question', sa.Text(), nullable=True, comment='用户问题'),
        sa.Column('reviewer_id', sa.Integer(), nullable=True, comment='审核人 ID'),
        sa.Column('review_result', sa.String(20), nullable=True, comment='审核结果：pass/improve/fail'),
        sa.Column('review_comment', sa.Text(), nullable=True, comment='审核意见'),
        sa.Column('problem_tags', sa.JSON(), nullable=True, comment="问题标签：['跑题', '术语堆砌', '编造']"),
        sa.Column('auto_add_to_dataset', sa.Integer(), nullable=True, default=0, comment='是否自动加入评测集'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 创建 prompt_versions 表
    op.create_table(
        'prompt_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('version', sa.String(50), nullable=True, comment='版本号'),
        sa.Column('prompt_content', sa.Text(), nullable=True, comment='完整 prompt 内容'),
        sa.Column('change_summary', sa.Text(), nullable=True, comment='变更摘要'),
        sa.Column('changed_rules', sa.JSON(), nullable=True, comment='变更的规则列表'),
        sa.Column('related_badcases', sa.JSON(), nullable=True, comment='关联的 badcase ID 列表'),
        sa.Column('created_by', sa.String(50), nullable=True, comment='创建人'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('prompt_versions')
    op.drop_table('prompt_reviews')
