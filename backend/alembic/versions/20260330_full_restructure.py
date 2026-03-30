"""full restructure: PostgreSQL, roles, audit log

Revision ID: 20260330_full_restructure
Revises: 20260329_update_users_password
Create Date: 2026-03-30
"""
import sqlalchemy as sa
from alembic import op

revision = "20260330_full_restructure"
down_revision = "20260329_update_users_password"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add new columns to users
    op.add_column("users", sa.Column("role", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=True))
    op.add_column("users", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("hashed_password", sa.String(255), nullable=True))

    # Copy plain password → hashed_password temporarily (will be re-seeded)
    op.execute("UPDATE users SET hashed_password = password, role = 'teacher', is_active = true, created_at = NOW()")

    # Make non-nullable now that values exist
    op.alter_column("users", "role", nullable=False)
    op.alter_column("users", "is_active", nullable=False)
    op.alter_column("users", "created_at", nullable=False)
    op.alter_column("users", "hashed_password", nullable=False)

    # Drop old plain password column
    op.drop_column("users", "password")

    # 2. Add audit columns to lessons
    op.add_column("lessons", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column("lessons", sa.Column(
        "updated_by_id",
        sa.Integer(),
        sa.ForeignKey("users.id"),
        nullable=True,
    ))

    # 3. Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
    )
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")
    op.drop_index("ix_audit_logs_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_column("lessons", "updated_by_id")
    op.drop_column("lessons", "updated_at")

    op.add_column("users", sa.Column("password", sa.String(), nullable=True))
    op.execute("UPDATE users SET password = hashed_password")
    op.alter_column("users", "password", nullable=False)
    op.drop_column("users", "hashed_password")
    op.drop_column("users", "created_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "role")