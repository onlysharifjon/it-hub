"""parent academic: grades, homework submissions, teacher feedback, events, certificates
+ users.phone/telegram, parents.avatar, homeworks.due_date

Revision ID: 20260709_parent_academic
Revises: 20260709_special_discounts
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = '20260709_parent_academic'
down_revision = '20260709_special_discounts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('phone', sa.String(30), nullable=True))
    op.add_column('users', sa.Column('telegram', sa.String(100), nullable=True))
    op.add_column('parents', sa.Column('avatar', sa.Text(), nullable=True))
    op.add_column('homeworks', sa.Column('due_date', sa.Date(), nullable=True))

    op.create_table(
        'homework_submissions',
        sa.Column('id',              sa.Integer(),  primary_key=True),
        sa.Column('homework_id',     sa.Integer(),  sa.ForeignKey('homeworks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id',      sa.Integer(),  sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status',          sa.String(20), nullable=False, server_default='pending'),
        sa.Column('grade',           sa.Integer(),  nullable=True),
        sa.Column('teacher_comment', sa.Text(),     nullable=True),
        sa.Column('submitted_at',    sa.DateTime(), nullable=True),
        sa.Column('created_at',      sa.DateTime(), nullable=False),
        sa.UniqueConstraint('homework_id', 'student_id', name='uq_homework_submission'),
    )
    op.create_index('ix_homework_submissions_homework_id', 'homework_submissions', ['homework_id'])
    op.create_index('ix_homework_submissions_student_id', 'homework_submissions', ['student_id'])

    op.create_table(
        'grades',
        sa.Column('id',            sa.Integer(),   primary_key=True),
        sa.Column('student_id',    sa.Integer(),   sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('group_id',      sa.Integer(),   sa.ForeignKey('groups.id'), nullable=True),
        sa.Column('subject',       sa.String(200), nullable=False),
        sa.Column('score',         sa.Integer(),   nullable=False),
        sa.Column('max_score',     sa.Integer(),   nullable=False, server_default='100'),
        sa.Column('exam_type',     sa.String(30),  nullable=False, server_default='exam'),
        sa.Column('exam_date',     sa.Date(),      nullable=False),
        sa.Column('comment',       sa.Text(),      nullable=True),
        sa.Column('created_by_id', sa.Integer(),   sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at',    sa.DateTime(),  nullable=False),
    )
    op.create_index('ix_grades_student_id', 'grades', ['student_id'])
    op.create_index('ix_grades_group_id', 'grades', ['group_id'])
    op.create_index('ix_grades_exam_date', 'grades', ['exam_date'])

    op.create_table(
        'teacher_feedbacks',
        sa.Column('id',         sa.Integer(),  primary_key=True),
        sa.Column('student_id', sa.Integer(),  sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('group_id',   sa.Integer(),  sa.ForeignKey('groups.id'), nullable=True),
        sa.Column('teacher_id', sa.Integer(),  sa.ForeignKey('users.id'), nullable=True),
        sa.Column('comment',    sa.Text(),     nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_teacher_feedbacks_student_id', 'teacher_feedbacks', ['student_id'])
    op.create_index('ix_teacher_feedbacks_created_at', 'teacher_feedbacks', ['created_at'])

    op.create_table(
        'events',
        sa.Column('id',            sa.Integer(),   primary_key=True),
        sa.Column('title',         sa.String(300), nullable=False),
        sa.Column('description',   sa.Text(),      nullable=True),
        sa.Column('event_date',    sa.DateTime(),  nullable=False),
        sa.Column('location',      sa.String(300), nullable=True),
        sa.Column('is_active',     sa.Boolean(),   nullable=False, server_default=sa.true()),
        sa.Column('created_by_id', sa.Integer(),   sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at',    sa.DateTime(),  nullable=False),
    )
    op.create_index('ix_events_event_date', 'events', ['event_date'])

    op.create_table(
        'certificates',
        sa.Column('id',            sa.Integer(),   primary_key=True),
        sa.Column('student_id',    sa.Integer(),   sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title',         sa.String(300), nullable=False),
        sa.Column('file_url',      sa.String(500), nullable=False),
        sa.Column('issued_at',     sa.Date(),      nullable=True),
        sa.Column('created_by_id', sa.Integer(),   sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at',    sa.DateTime(),  nullable=False),
    )
    op.create_index('ix_certificates_student_id', 'certificates', ['student_id'])


def downgrade() -> None:
    op.drop_table('certificates')
    op.drop_table('events')
    op.drop_table('teacher_feedbacks')
    op.drop_table('grades')
    op.drop_table('homework_submissions')
    op.drop_column('homeworks', 'due_date')
    op.drop_column('parents', 'avatar')
    op.drop_column('users', 'telegram')
    op.drop_column('users', 'phone')
