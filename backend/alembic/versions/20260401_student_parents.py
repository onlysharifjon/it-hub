"""student parent contacts: phone2 -> father/mother fields

Revision ID: 20260401_student_parents
Revises: 20260331_add_category
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa

revision = '20260401_student_parents'
down_revision = '20260331_add_category'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('students', 'phone2')
    op.add_column('students', sa.Column('father_name',  sa.String(200), nullable=True))
    op.add_column('students', sa.Column('father_phone', sa.String(20),  nullable=True))
    op.add_column('students', sa.Column('mother_name',  sa.String(200), nullable=True))
    op.add_column('students', sa.Column('mother_phone', sa.String(20),  nullable=True))


def downgrade():
    op.drop_column('students', 'mother_phone')
    op.drop_column('students', 'mother_name')
    op.drop_column('students', 'father_phone')
    op.drop_column('students', 'father_name')
    op.add_column('students', sa.Column('phone2', sa.String(20), nullable=True))
