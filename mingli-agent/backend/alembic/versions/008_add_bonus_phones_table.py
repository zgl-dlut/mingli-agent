"""add bonus_phones table for persistent whitelist

Revision ID: 008_bonus_phones
Revises: 007_add_prompt_review_tables
Create Date: 2026-08-21 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '008_bonus_phones'
down_revision = '508b12ccf9f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'bonus_phones',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('phone', sa.String(20), unique=True, nullable=False, comment='白名单手机号'),
        sa.Column('points', sa.Integer(), server_default='1000', nullable=False, comment='赠送积分数'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('bonus_phones')
