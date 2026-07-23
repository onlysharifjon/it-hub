"""add camera_attendance table

Revision ID: 20260709_add_camera_attendance
Revises: 20260704_add_student_photo
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = '20260709_add_camera_attendance'
down_revision = '20260704_add_student_photo'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'camera_attendance',
        sa.Column('id',          sa.Integer(),     primary_key=True, index=True),
        sa.Column('student_id',  sa.Integer(),     sa.ForeignKey('students.id'), nullable=True),
        sa.Column('staff_id',    sa.Integer(),     sa.ForeignKey('users.id'),    nullable=True),
        sa.Column('person_type', sa.String(20),    nullable=False),
        sa.Column('event_type',  sa.String(10),    nullable=False),
        sa.Column('detected_at', sa.DateTime(),    nullable=False),
    )
    op.create_index('ix_camera_attendance_student_id', 'camera_attendance', ['student_id'])
    op.create_index('ix_camera_attendance_detected_at', 'camera_attendance', ['detected_at'])


def downgrade() -> None:
    op.drop_table('camera_attendance')
