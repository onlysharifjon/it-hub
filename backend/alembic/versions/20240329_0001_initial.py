"""initial

Revision ID: 20240329_0001
Revises:
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20240329_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lessons",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("lesson_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("section", sa.String(), nullable=True),
        sa.Column("guide", sa.String(), nullable=True),
        sa.Column("homework", sa.String(), nullable=True),
        sa.Column("extra_notes", sa.String(), nullable=True),
    )
    op.create_index("ix_lessons_id", "lessons", ["id"], unique=False)
    op.create_index("ix_lessons_lesson_number", "lessons", ["lesson_number"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_lessons_lesson_number", table_name="lessons")
    op.drop_index("ix_lessons_id", table_name="lessons")
    op.drop_table("lessons")

