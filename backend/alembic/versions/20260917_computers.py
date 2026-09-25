"""computers + computer_rentals (kompyuter berish jurnali)

Revision ID: 20260917_computers
Revises: 20260904_lead_phone_key
Create Date: 2026-09-17
"""
import sqlalchemy as sa
from alembic import op

revision = "20260917_computers"
down_revision = "20260904_lead_phone_key"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "computers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_computers_id", "computers", ["id"])
    op.create_index("ix_computers_number", "computers", ["number"], unique=True)

    op.create_table(
        "computer_rentals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("computer_id", sa.Integer(), sa.ForeignKey("computers.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("given_at", sa.DateTime(), nullable=False),
        sa.Column("returned_at", sa.DateTime(), nullable=True),
        sa.Column("given_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("returned_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("return_note", sa.Text(), nullable=True),
    )
    op.create_index("ix_computer_rentals_id", "computer_rentals", ["id"])
    op.create_index("ix_computer_rentals_computer_id", "computer_rentals", ["computer_id"])
    op.create_index("ix_computer_rentals_student_id", "computer_rentals", ["student_id"])
    op.create_index("ix_computer_rentals_given_at", "computer_rentals", ["given_at"])
    op.create_index("ix_computer_rentals_returned_at", "computer_rentals", ["returned_at"])


def downgrade():
    op.drop_table("computer_rentals")
    op.drop_table("computers")
