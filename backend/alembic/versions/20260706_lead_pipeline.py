"""lead pipeline: stages, sources, activities

Revision ID: 20260706_lead_pipeline
Revises: 20260704_add_discounts
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = '20260706_lead_pipeline'
down_revision = '20260704_add_discounts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'lead_stages',
        sa.Column('id',          sa.Integer(),   primary_key=True),
        sa.Column('name',        sa.String(80),  nullable=False),
        sa.Column('slug',        sa.String(80),  nullable=False),
        sa.Column('order',       sa.Integer(),   nullable=False, server_default='0'),
        sa.Column('color',       sa.String(20),  nullable=False, server_default='slate'),
        sa.Column('icon',        sa.String(40),  nullable=False, server_default='circle'),
        sa.Column('kind',        sa.String(10),  nullable=False, server_default='lead'),
        sa.Column('is_archived', sa.Boolean(),   nullable=False, server_default=sa.false()),
        sa.Column('created_at',  sa.DateTime(),  nullable=False),
    )
    op.create_index('ix_lead_stages_slug', 'lead_stages', ['slug'], unique=True)

    op.create_table(
        'lead_sources',
        sa.Column('id',          sa.Integer(),   primary_key=True),
        sa.Column('name',        sa.String(80),  nullable=False),
        sa.Column('is_campaign', sa.Boolean(),   nullable=False, server_default=sa.false()),
        sa.Column('is_default',  sa.Boolean(),   nullable=False, server_default=sa.false()),
        sa.Column('is_active',   sa.Boolean(),   nullable=False, server_default=sa.true()),
        sa.Column('created_at',  sa.DateTime(),  nullable=False),
    )

    op.create_table(
        'lead_activities',
        sa.Column('id',          sa.Integer(),   primary_key=True),
        sa.Column('lead_id',     sa.Integer(),   sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action',      sa.String(40),  nullable=False),
        sa.Column('description', sa.Text(),      nullable=True),
        sa.Column('author_id',   sa.Integer(),   sa.ForeignKey('users.id'), nullable=True),
        sa.Column('meta_json',   sa.Text(),      nullable=True),
        sa.Column('created_at',  sa.DateTime(),  nullable=False),
    )
    op.create_index('ix_lead_activities_lead_id', 'lead_activities', ['lead_id'])

    with op.batch_alter_table('leads') as batch:
        batch.add_column(sa.Column('stage_id',  sa.Integer(), sa.ForeignKey('lead_stages.id'),  nullable=True))
        batch.add_column(sa.Column('source_id', sa.Integer(), sa.ForeignKey('lead_sources.id'), nullable=True))
    op.create_index('ix_leads_stage_id', 'leads', ['stage_id'])


def downgrade() -> None:
    op.drop_index('ix_leads_stage_id', 'leads')
    with op.batch_alter_table('leads') as batch:
        batch.drop_column('source_id')
        batch.drop_column('stage_id')
    op.drop_index('ix_lead_activities_lead_id', 'lead_activities')
    op.drop_table('lead_activities')
    op.drop_table('lead_sources')
    op.drop_index('ix_lead_stages_slug', 'lead_stages')
    op.drop_table('lead_stages')
