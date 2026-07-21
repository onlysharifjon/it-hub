"""lead rich fields, shared pool/claim, intake forms

Revision ID: 20260706_rich_intake
Revises: 20260706_reminders_notif
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = '20260706_rich_intake'
down_revision = '20260706_reminders_notif'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('leads') as batch:
        batch.add_column(sa.Column('date_of_birth',       sa.Date(),     nullable=True))
        batch.add_column(sa.Column('parent_phone',        sa.String(30), nullable=True))
        batch.add_column(sa.Column('parent2_phone',       sa.String(30), nullable=True))
        batch.add_column(sa.Column('interested_group_id', sa.Integer(),  sa.ForeignKey('groups.id'), nullable=True))
        batch.add_column(sa.Column('is_shared',           sa.Boolean(),  nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column('claimed_by_id',       sa.Integer(),  sa.ForeignKey('users.id'), nullable=True))
        batch.add_column(sa.Column('claimed_at',          sa.DateTime(), nullable=True))
    op.create_index('ix_leads_is_shared', 'leads', ['is_shared'])
    op.create_index('ix_leads_claimed_by_id', 'leads', ['claimed_by_id'])

    op.create_table(
        'intake_forms',
        sa.Column('id',          sa.Integer(),   primary_key=True),
        sa.Column('slug',        sa.String(60),  nullable=False),
        sa.Column('name',        sa.String(150), nullable=False),
        sa.Column('title',       sa.String(200), nullable=True),
        sa.Column('description', sa.Text(),      nullable=True),
        sa.Column('source_id',   sa.Integer(),   sa.ForeignKey('lead_sources.id'), nullable=True),
        sa.Column('is_active',   sa.Boolean(),   nullable=False, server_default=sa.true()),
        sa.Column('submissions', sa.Integer(),   nullable=False, server_default='0'),
        sa.Column('created_at',  sa.DateTime(),  nullable=False),
    )
    op.create_index('ix_intake_forms_slug', 'intake_forms', ['slug'], unique=True)


def downgrade() -> None:
    op.drop_table('intake_forms')
    op.drop_index('ix_leads_claimed_by_id', 'leads')
    op.drop_index('ix_leads_is_shared', 'leads')
    with op.batch_alter_table('leads') as batch:
        for col in ('claimed_at', 'claimed_by_id', 'is_shared', 'interested_group_id',
                    'parent2_phone', 'parent_phone', 'date_of_birth'):
            batch.drop_column(col)
