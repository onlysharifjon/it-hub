"""add leads table

Revision ID: 20260629_add_leads
Revises: 20260626_add_avatar
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa

revision = '20260629_add_leads'
down_revision = '20260626_add_avatar'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'leads',
        sa.Column('id',              sa.Integer(),     primary_key=True),
        sa.Column('full_name',       sa.String(200),   nullable=False),
        sa.Column('phone',           sa.String(30),    nullable=False),
        sa.Column('course_interest', sa.String(100),   nullable=True),
        sa.Column('status',          sa.String(30),    nullable=False, server_default='new'),
        sa.Column('callback_at',     sa.DateTime(),    nullable=True),
        sa.Column('notes',           sa.Text(),        nullable=True),
        sa.Column('created_by_id',   sa.Integer(),     sa.ForeignKey('users.id'), nullable=False),
        sa.Column('updated_by_id',   sa.Integer(),     sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at',      sa.DateTime(),    nullable=False),
        sa.Column('updated_at',      sa.DateTime(),    nullable=True),
    )
    op.create_index('ix_leads_status', 'leads', ['status'])


def downgrade() -> None:
    op.drop_index('ix_leads_status', 'leads')
    op.drop_table('leads')
