"""student_visits (Notifications: keldi/ketdi) + students.telegram_user_id, students.photo

Revision ID: 20260709_student_visits
Revises: 20260709_parent_academic
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = '20260709_student_visits'
down_revision = '20260709_parent_academic'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'student_visits',
        sa.Column('id',             sa.Integer(),   primary_key=True),
        sa.Column('student_id',     sa.Integer(),   sa.ForeignKey('students.id'), nullable=False),
        sa.Column('kind',           sa.String(10),  nullable=False),
        sa.Column('noted_by_id',    sa.Integer(),   sa.ForeignKey('users.id'), nullable=True),
        sa.Column('telegram_sent',  sa.Boolean(),   nullable=False, server_default=sa.false()),
        sa.Column('telegram_error', sa.String(500), nullable=True),
        sa.Column('created_at',     sa.DateTime(),  nullable=False),
    )
    op.create_index('ix_student_visits_student_id', 'student_visits', ['student_id'])
    op.create_index('ix_student_visits_created_at', 'student_visits', ['created_at'])

    op.add_column('students', sa.Column('telegram_user_id', sa.String(50), nullable=True))
    op.add_column('students', sa.Column('photo', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('students', 'photo')
    op.drop_column('students', 'telegram_user_id')
    op.drop_table('student_visits')
