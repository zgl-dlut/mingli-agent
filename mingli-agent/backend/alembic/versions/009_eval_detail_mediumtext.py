"""change eval_results.detail from TEXT to MEDIUMTEXT to store full report JSON

Revision ID: 009_eval_detail_mt
Revises: 008_bonus_phones
Create Date: 2026-08-29 23:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT

# revision identifiers, used by Alembic.
revision = '009_eval_detail_mt'
down_revision = '008_bonus_phones'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # TEXT 最大 64KB，存完整报告 JSON 不够用，升级为 MEDIUMTEXT（16MB）
    op.alter_column('eval_results', 'detail',
        existing_type=sa.Text(),
        type_=MEDIUMTEXT(),
        existing_nullable=True,
        comment='详细结果JSON（含完整报告report、违规明细violations、归因root_cause、分层复核layer_reviews）')


def downgrade() -> None:
    op.alter_column('eval_results', 'detail',
        existing_type=MEDIUMTEXT(),
        type_=sa.Text(),
        existing_nullable=True)
