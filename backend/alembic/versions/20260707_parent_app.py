"""parent mobile app: parents, children link, tokens, notifications, schedule slots, invoices

Revision ID: 20260707_parent_app
Revises: 20260707_pay_recorded_by
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa

revision = '20260707_parent_app'
down_revision = '20260707_pay_recorded_by'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'parents',
        sa.Column('id',              sa.Integer(),   primary_key=True),
        sa.Column('full_name',       sa.String(200), nullable=False),
        sa.Column('display_name',    sa.String(120), nullable=True),
        sa.Column('phone',           sa.String(30),  nullable=False),
        sa.Column('username',        sa.String(100), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active',       sa.Boolean(),   nullable=False, server_default=sa.true()),
        sa.Column('created_by_id',   sa.Integer(),   sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at',      sa.DateTime(),  nullable=False),
    )
    op.create_index('ix_parents_phone', 'parents', ['phone'], unique=True)
    op.create_index('ix_parents_username', 'parents', ['username'], unique=True)

    op.create_table(
        'parent_children',
        sa.Column('id',         sa.Integer(),  primary_key=True),
        sa.Column('parent_id',  sa.Integer(),  sa.ForeignKey('parents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', sa.Integer(),  sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('parent_id', 'student_id', name='uq_parent_child'),
    )
    op.create_index('ix_parent_children_parent_id', 'parent_children', ['parent_id'])
    op.create_index('ix_parent_children_student_id', 'parent_children', ['student_id'])

    op.create_table(
        'parent_refresh_tokens',
        sa.Column('id',         sa.Integer(),   primary_key=True),
        sa.Column('parent_id',  sa.Integer(),   sa.ForeignKey('parents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(128), nullable=False),
        sa.Column('expires_at', sa.DateTime(),  nullable=False),
        sa.Column('revoked_at', sa.DateTime(),  nullable=True),
        sa.Column('created_at', sa.DateTime(),  nullable=False),
    )
    op.create_index('ix_parent_refresh_tokens_parent_id', 'parent_refresh_tokens', ['parent_id'])
    op.create_index('ix_parent_refresh_tokens_token_hash', 'parent_refresh_tokens', ['token_hash'], unique=True)

    op.create_table(
        'parent_notifications',
        sa.Column('id',         sa.Integer(),   primary_key=True),
        sa.Column('parent_id',  sa.Integer(),   sa.ForeignKey('parents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', sa.Integer(),   sa.ForeignKey('students.id'), nullable=True),
        sa.Column('type',       sa.String(20),  nullable=False, server_default='payment'),
        sa.Column('title',      sa.String(200), nullable=False),
        sa.Column('body',       sa.Text(),      nullable=True),
        sa.Column('created_at', sa.DateTime(),  nullable=False),
        sa.Column('read_at',    sa.DateTime(),  nullable=True),
    )
    op.create_index('ix_parent_notifications_parent_id', 'parent_notifications', ['parent_id'])
    op.create_index('ix_parent_notifications_created_at', 'parent_notifications', ['created_at'])

    op.create_table(
        'schedule_slots',
        sa.Column('id',          sa.Integer(),  primary_key=True),
        sa.Column('group_id',    sa.Integer(),  sa.ForeignKey('groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('day_of_week', sa.Integer(),  nullable=False),
        sa.Column('start_time',  sa.String(5),  nullable=False),
        sa.Column('end_time',    sa.String(5),  nullable=False),
        sa.Column('room',        sa.String(50), nullable=True),
        sa.Column('created_at',  sa.DateTime(), nullable=False),
    )
    op.create_index('ix_schedule_slots_group_id', 'schedule_slots', ['group_id'])

    op.create_table(
        'parent_invoices',
        sa.Column('id',           sa.Integer(),    primary_key=True),
        sa.Column('parent_id',    sa.Integer(),    sa.ForeignKey('parents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id',   sa.Integer(),    sa.ForeignKey('students.id'), nullable=False),
        sa.Column('group_id',     sa.Integer(),    sa.ForeignKey('groups.id'), nullable=False),
        sa.Column('amount',       sa.Numeric(12, 2), nullable=False),
        sa.Column('provider',     sa.String(20),   nullable=False, server_default='payme'),
        sa.Column('status',       sa.String(20),   nullable=False, server_default='pending'),
        sa.Column('checkout_ref', sa.String(120),  nullable=True),
        sa.Column('created_at',   sa.DateTime(),   nullable=False),
    )
    op.create_index('ix_parent_invoices_parent_id', 'parent_invoices', ['parent_id'])


def downgrade() -> None:
    op.drop_table('parent_invoices')
    op.drop_table('schedule_slots')
    op.drop_table('parent_notifications')
    op.drop_table('parent_refresh_tokens')
    op.drop_table('parent_children')
    op.drop_index('ix_parents_username', 'parents')
    op.drop_index('ix_parents_phone', 'parents')
    op.drop_table('parents')
