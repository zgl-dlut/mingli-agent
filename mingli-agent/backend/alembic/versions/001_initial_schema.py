"""初始数据库 schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users 表
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('phone', sa.String(20), nullable=False, comment='手机号'),
        sa.Column('email', sa.String(255), nullable=True, comment='邮箱'),
        sa.Column('hashed_password', sa.String(255), nullable=True, comment='密码哈希'),
        sa.Column('name', sa.String(100), server_default='用户', nullable=False, comment='用户名'),
        sa.Column('avatar', sa.String(500), nullable=True, comment='头像URL'),
        sa.Column('points', sa.Integer(), server_default='0', nullable=False, comment='积分余额'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone'),
        sa.UniqueConstraint('email'),
    )

    # persons 表
    op.create_table(
        'persons',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('gender', sa.String(10), nullable=False),
        sa.Column('birth_date', sa.String(20), nullable=False),
        sa.Column('birth_time', sa.String(20), nullable=False),
        sa.Column('birth_location', sa.String(200), nullable=False),
        sa.Column('birth_lat', sa.Float(), nullable=False),
        sa.Column('birth_lng', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_persons_user_id', 'persons', ['user_id'])

    # chat_sessions 表
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=False),
        sa.Column('bazi_data_json', sa.JSON(), nullable=True),
        sa.Column('astro_data_json', sa.JSON(), nullable=True),
        sa.Column('title', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_chat_sessions_person_id', 'chat_sessions', ['person_id'])

    # chat_messages 表
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_chat_messages_session_id', 'chat_messages', ['session_id'])

    # orders 表
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('pay_method', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('trade_no', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_orders_user_id', 'orders', ['user_id'])

    # transactions 表
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_transactions_user_id', 'transactions', ['user_id'])


def downgrade() -> None:
    op.drop_table('transactions')
    op.drop_table('orders')
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
    op.drop_table('persons')
    op.drop_table('users')
