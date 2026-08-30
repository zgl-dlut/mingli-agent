"""add bazi_data_json to persons

Revision ID: 005_bazi_data
Revises: 004_format_error
Create Date: 2026-08-13 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005_bazi_data'
down_revision = '004_format_error'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 为 persons 表添加 bazi_data_json 字段
    op.add_column(
        'persons',
        sa.Column('bazi_data_json', sa.JSON(), nullable=True, 
                  comment='完整排盘数据（包括命格箴言）')
    )


def downgrade() -> None:
    # 删除 bazi_data_json 字段
    op.drop_column('persons', 'bazi_data_json')
