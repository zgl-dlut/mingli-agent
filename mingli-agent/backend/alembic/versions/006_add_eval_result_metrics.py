"""add eval_type and metrics columns to eval_results

Revision ID: 006_eval_metrics
Revises: 005_bazi_data
Create Date: 2026-08-14 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006_eval_metrics'
down_revision = '005_bazi_data'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('eval_results', sa.Column('eval_type', sa.String(50), nullable=True,
        comment='评测类型: report_quality/chart_accuracy/badcase_eval/production_monitor'))
    op.add_column('eval_results', sa.Column('match_count', sa.Integer(), nullable=True,
        comment='检测匹配数（预期结果与实际结果一致的数量）'))
    op.add_column('eval_results', sa.Column('match_rate', sa.Float(), nullable=True,
        comment='检测准确率（检测匹配数/总数）'))
    op.add_column('eval_results', sa.Column('task_completion_rate', sa.JSON(), nullable=True,
        comment='任务完成率: {l1_technical, l2_format, l3_quality, l4_satisfaction, overall}'))
    op.add_column('eval_results', sa.Column('accuracy_rate', sa.JSON(), nullable=True,
        comment='正确率: {chart, structure, narrative, logic, consistency, safety, overall}'))
    op.add_column('eval_results', sa.Column('soft_score', sa.JSON(), nullable=True,
        comment='软性评分: {narrative, fluency, storytelling, bold_rationality, terminology_popularization, avg}'))
    op.add_column('eval_results', sa.Column('violation_distribution', sa.JSON(), nullable=True,
        comment='违规分布: {违规类型: 计数}'))


def downgrade() -> None:
    op.drop_column('eval_results', 'violation_distribution')
    op.drop_column('eval_results', 'soft_score')
    op.drop_column('eval_results', 'accuracy_rate')
    op.drop_column('eval_results', 'task_completion_rate')
    op.drop_column('eval_results', 'match_rate')
    op.drop_column('eval_results', 'match_count')
    op.drop_column('eval_results', 'eval_type')
