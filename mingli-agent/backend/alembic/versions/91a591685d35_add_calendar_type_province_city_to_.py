"""add calendar_type province city to persons

Revision ID: 91a591685d35
Revises: 001_initial
Create Date: 2026-08-06 19:08:55.666050

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '91a591685d35'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 新增3列，server_default 确保现有数据可填充
    op.add_column('persons', sa.Column('calendar_type', sa.String(length=10), nullable=False, server_default='solar'))
    op.add_column('persons', sa.Column('province', sa.String(length=50), nullable=False, server_default=''))
    op.add_column('persons', sa.Column('city', sa.String(length=50), nullable=False, server_default=''))


def downgrade() -> None:
    op.drop_column('persons', 'city')
    op.drop_column('persons', 'province')
    op.drop_column('persons', 'calendar_type')
