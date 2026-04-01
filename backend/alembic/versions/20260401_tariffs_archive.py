"""add tariffs table, is_archived to students, tariff_id to group_students

Revision ID: 20260401_tariffs_archive
Revises: 20260401_group_stage
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa

revision = '20260401_tariffs_archive'
down_revision = '20260401_group_stage'
branch_labels = None
depends_on = None


def upgrade():
    # Create tariffs table
    op.create_table(
        'tariffs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('price', sa.Numeric(12, 2), nullable=False, server_default='100000'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # Add is_archived to students
    op.add_column('students', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'))

    # Add tariff_id to group_students
    op.add_column('group_students', sa.Column('tariff_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_group_students_tariff', 'group_students', 'tariffs', ['tariff_id'], ['id'])

    # Insert default tariff
    op.execute("INSERT INTO tariffs (name, price, description) VALUES ('Standart tarif', 100000, 'Har oylik standart tolov')")


def downgrade():
    op.drop_constraint('fk_group_students_tariff', 'group_students', type_='foreignkey')
    op.drop_column('group_students', 'tariff_id')
    op.drop_column('students', 'is_archived')
    op.drop_table('tariffs')
