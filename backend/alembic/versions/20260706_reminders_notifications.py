"""reminders + notifications

Revision ID: 20260706_reminders_notif
Revises: 20260706_lead_pipeline
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = '20260706_reminders_notif'
down_revision = '20260706_lead_pipeline'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'reminders',
        sa.Column('id',             sa.Integer(),  primary_key=True),
        sa.Column('lead_id',        sa.Integer(),  sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assigned_to_id', sa.Integer(),  sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_by_id',  sa.Integer(),  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('due_at',         sa.DateTime(), nullable=False),
        sa.Column('body',           sa.Text(),     nullable=True),
        sa.Column('kind',           sa.String(20), nullable=False, server_default='call'),
        sa.Column('status',         sa.String(20), nullable=False, server_default='pending'),
        sa.Column('snoozed_until',  sa.DateTime(), nullable=True),
        sa.Column('done_at',        sa.DateTime(), nullable=True),
        sa.Column('created_at',     sa.DateTime(), nullable=False),
        sa.Column('updated_at',     sa.DateTime(), nullable=True),
    )
    op.create_index('ix_reminders_lead_id', 'reminders', ['lead_id'])
    op.create_index('ix_reminders_assigned_to_id', 'reminders', ['assigned_to_id'])
    op.create_index('ix_reminders_status', 'reminders', ['status'])
    op.create_index('ix_reminders_due_at', 'reminders', ['due_at'])

    op.create_table(
        'notifications',
        sa.Column('id',                sa.Integer(),   primary_key=True),
        sa.Column('user_id',           sa.Integer(),   sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('notification_type', sa.String(40),  nullable=False, server_default='new_lead'),
        sa.Column('title',             sa.String(200), nullable=False),
        sa.Column('body',              sa.Text(),      nullable=True),
        sa.Column('link',              sa.String(200), nullable=True),
        sa.Column('is_read',           sa.Boolean(),   nullable=False, server_default=sa.false()),
        sa.Column('created_at',        sa.DateTime(),  nullable=False),
    )
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_is_read', 'notifications', ['is_read'])


def downgrade() -> None:
    op.drop_table('notifications')
    op.drop_table('reminders')
