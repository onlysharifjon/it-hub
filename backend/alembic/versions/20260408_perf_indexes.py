"""add composite indexes for performance

Revision ID: 20260408_perf_indexes
Revises: 20260401_user_block_expiry
Create Date: 2026-04-08
"""

from alembic import op

revision = '20260408_perf_indexes'
down_revision = '20260401_user_block_expiry'
branch_labels = None
depends_on = None


def upgrade():
    # attendance — eng ko'p ishlatiladigan jadval
    op.create_index('idx_att_group_date',     'attendance', ['group_id', 'lesson_date'])
    op.create_index('idx_att_group_student',  'attendance', ['group_id', 'student_id'])
    op.create_index('idx_att_student_present','attendance', ['student_id', 'is_present'])
    op.create_index('idx_att_year_month',     'attendance', ['group_id', 'is_present', 'lesson_date'])

    # payments
    op.create_index('idx_pay_group_month',    'payments',   ['group_id', 'month', 'year'])
    op.create_index('idx_pay_student_month',  'payments',   ['student_id', 'month', 'year'])

    # groups
    op.create_index('idx_grp_teacher_active', 'groups',     ['teacher_id', 'is_active'])

    # group_students — foreign key lookups
    op.create_index('idx_gs_group',           'group_students', ['group_id'])
    op.create_index('idx_gs_student',         'group_students', ['student_id'])

    # audit_logs
    op.create_index('idx_audit_entity',       'audit_logs', ['entity_type', 'entity_id', 'changed_at'])

    # students
    op.create_index('idx_stu_active_arch',    'students',   ['is_active', 'is_archived', 'created_at'])


def downgrade():
    op.drop_index('idx_att_group_date',      'attendance')
    op.drop_index('idx_att_group_student',   'attendance')
    op.drop_index('idx_att_student_present', 'attendance')
    op.drop_index('idx_att_year_month',      'attendance')
    op.drop_index('idx_pay_group_month',     'payments')
    op.drop_index('idx_pay_student_month',   'payments')
    op.drop_index('idx_grp_teacher_active',  'groups')
    op.drop_index('idx_gs_group',            'group_students')
    op.drop_index('idx_gs_student',          'group_students')
    op.drop_index('idx_audit_entity',        'audit_logs')
    op.drop_index('idx_stu_active_arch',     'students')
