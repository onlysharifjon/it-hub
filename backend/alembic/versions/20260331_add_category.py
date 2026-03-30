"""Add category to lessons, drop month/week, clear all lessons

Revision ID: 20260331_add_category
Revises: 20260331_merge
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa

revision = '20260331_add_category'
down_revision = '20260331_merge'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Delete all existing lessons (clean slate)
    op.execute("DELETE FROM lessons")

    # 2. Drop old unique index/constraint on lesson_number
    op.execute("ALTER TABLE lessons DROP CONSTRAINT IF EXISTS lessons_lesson_number_key")
    op.execute("DROP INDEX IF EXISTS ix_lessons_lesson_number")

    # 3. Drop month and week columns
    op.drop_column('lessons', 'month')
    op.drop_column('lessons', 'week')

    # 4. Add category column
    op.add_column('lessons', sa.Column('category', sa.String(50), nullable=False, server_default='foundation'))

    # 5. Add unique constraint on (category, lesson_number)
    op.create_unique_constraint('uq_lesson_category_number', 'lessons', ['category', 'lesson_number'])

    # 6. Add a regular index on lesson_number for ordering queries
    op.create_index('ix_lessons_lesson_number', 'lessons', ['lesson_number'])


def downgrade():
    op.drop_index('ix_lessons_lesson_number', table_name='lessons')
    op.drop_constraint('uq_lesson_category_number', 'lessons', type_='unique')
    op.drop_column('lessons', 'category')
    op.add_column('lessons', sa.Column('month', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('lessons', sa.Column('week', sa.Integer(), nullable=False, server_default='1'))
    op.create_unique_constraint('lessons_lesson_number_key', 'lessons', ['lesson_number'])
