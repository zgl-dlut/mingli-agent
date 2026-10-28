"""add V3 unified reports

Revision ID: 012_v3_reports
Revises: 011_v3_profile_subscription
Create Date: 2026-10-28 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "012_v3_reports"
down_revision = "011_v3_profile_subscription"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("identity_key", sa.String(255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("primary_person_id", sa.Integer(), nullable=False),
        sa.Column("secondary_person_id", sa.Integer(), nullable=True),
        sa.Column("report_type", sa.String(32), nullable=False),
        sa.Column("period_key", sa.String(16), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("preview_json", sa.JSON(), nullable=True),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("chart_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("prompt_version", sa.String(64), server_default="v3-report-1", nullable=False),
        sa.Column("source_message_id", sa.Integer(), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity_key", name="uq_reports_identity_key"),
        sa.UniqueConstraint("source_message_id", name="uq_reports_source_message_id"),
    )
    op.create_index("ix_reports_user_person", "reports", ["user_id", "primary_person_id"])
    op.create_index(
        "ix_reports_user_type_status",
        "reports",
        ["user_id", "report_type", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_reports_user_type_status", table_name="reports")
    op.drop_index("ix_reports_user_person", table_name="reports")
    op.drop_table("reports")
