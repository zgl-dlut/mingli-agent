"""add V3 profile, subscription, and usage foundations

Revision ID: 011_v3_profile_subscription
Revises: 010_content_unlocks
Create Date: 2026-10-28 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "011_v3_profile_subscription"
down_revision = "010_content_unlocks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "persons",
        sa.Column("is_self", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "persons",
        sa.Column("relationship_type", sa.String(20), server_default="other", nullable=False),
    )
    op.add_column("persons", sa.Column("relationship_note", sa.String(200), nullable=True))
    op.add_column("persons", sa.Column("consent_confirmed_at", sa.DateTime(), nullable=True))
    op.add_column("persons", sa.Column("chart_snapshot_json", sa.JSON(), nullable=True))
    op.add_column("persons", sa.Column("chart_snapshot_version", sa.String(32), nullable=True))
    op.add_column("persons", sa.Column("chart_snapshot_updated_at", sa.DateTime(), nullable=True))
    op.create_index("ix_persons_user_self", "persons", ["user_id", "is_self"])

    if op.get_bind().dialect.name == "mysql":
        op.execute(
            sa.text(
                """
                UPDATE persons AS p
                JOIN (
                    SELECT user_id, MIN(id) AS self_id
                    FROM persons
                    GROUP BY user_id
                ) AS first_person ON first_person.user_id = p.user_id
                SET p.is_self = CASE WHEN p.id = first_person.self_id THEN 1 ELSE 0 END
                """
            )
        )
    else:
        op.execute(
            sa.text(
                """
                UPDATE persons
                SET is_self = CASE
                    WHEN id = (
                        SELECT MIN(p2.id)
                        FROM persons AS p2
                        WHERE p2.user_id = persons.user_id
                    ) THEN 1
                    ELSE 0
                END
                """
            )
        )
    op.execute(
        sa.text(
            "UPDATE persons SET relationship_type = "
            "CASE WHEN is_self = 1 THEN 'self' ELSE 'other' END"
        )
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_code", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("source", sa.String(20), server_default="mock", nullable=False),
        sa.Column("billing_cycle", sa.String(20), server_default="monthly", nullable=False),
        sa.Column("starts_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscriptions_user_status", "subscriptions", ["user_id", "status"])
    op.create_index("ix_subscriptions_expires_at", "subscriptions", ["expires_at"])

    op.create_table(
        "usage_counters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("metric", sa.String(40), nullable=False),
        sa.Column("period_key", sa.String(20), nullable=False),
        sa.Column("scope_id", sa.String(64), server_default="", nullable=False),
        sa.Column("count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "metric",
            "period_key",
            "scope_id",
            name="uq_usage_counter_identity",
        ),
    )
    op.create_index("ix_usage_counters_user_id", "usage_counters", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_usage_counters_user_id", table_name="usage_counters")
    op.drop_table("usage_counters")
    op.drop_index("ix_subscriptions_expires_at", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_status", table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index("ix_persons_user_self", table_name="persons")
    op.drop_column("persons", "chart_snapshot_updated_at")
    op.drop_column("persons", "chart_snapshot_version")
    op.drop_column("persons", "chart_snapshot_json")
    op.drop_column("persons", "consent_confirmed_at")
    op.drop_column("persons", "relationship_note")
    op.drop_column("persons", "relationship_type")
    op.drop_column("persons", "is_self")
