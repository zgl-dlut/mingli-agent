"""add V3 persona, memory, and safety domain

Revision ID: 013_v3_persona
Revises: 012_v3_reports
Create Date: 2026-10-28 13:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "013_v3_persona"
down_revision = "012_v3_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "personas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("avatar_key", sa.String(40), nullable=False),
        sa.Column("profile_json", sa.JSON(), nullable=False),
        sa.Column("prompt_version", sa.String(64), server_default="v3-persona-1", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("person_id", name="uq_personas_person_id"),
    )
    op.create_index("ix_personas_user_id", "personas", ["user_id"])

    op.create_table(
        "persona_conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("persona_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(120), server_default="新的对话", nullable=False),
        sa.Column("user_turn_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_persona_conversations_user_id", "persona_conversations", ["user_id"])
    op.create_index(
        "ix_persona_conversations_persona_recent",
        "persona_conversations",
        ["persona_id", "last_message_at"],
    )

    op.create_table(
        "persona_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("safety_category", sa.String(32), nullable=True),
        sa.Column("prompt_version", sa.String(64), server_default="v3-persona-1", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_persona_messages_user_id", "persona_messages", ["user_id"])
    op.create_index(
        "ix_persona_messages_conversation_created",
        "persona_messages",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "persona_memories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("persona_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("persona_id", name="uq_persona_memories_persona_id"),
    )
    op.create_index("ix_persona_memories_user_id", "persona_memories", ["user_id"])

    op.create_table(
        "safety_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("persona_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_safety_events_user_created", "safety_events", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_safety_events_user_created", table_name="safety_events")
    op.drop_table("safety_events")
    op.drop_index("ix_persona_memories_user_id", table_name="persona_memories")
    op.drop_table("persona_memories")
    op.drop_index("ix_persona_messages_conversation_created", table_name="persona_messages")
    op.drop_index("ix_persona_messages_user_id", table_name="persona_messages")
    op.drop_table("persona_messages")
    op.drop_index("ix_persona_conversations_persona_recent", table_name="persona_conversations")
    op.drop_index("ix_persona_conversations_user_id", table_name="persona_conversations")
    op.drop_table("persona_conversations")
    op.drop_index("ix_personas_user_id", table_name="personas")
    op.drop_table("personas")
