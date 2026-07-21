"""holidays (dam olish kunlari), homeworks (uy vazifasi + telegram), groups.telegram_chat_id

Revision ID: 20260709_holidays_homework
Revises: 20260707_parent_app
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = '20260709_holidays_homework'
down_revision = '20260707_parent_app'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'holidays',
        sa.Column('id',            sa.Integer(),   primary_key=True),
        sa.Column('name',          sa.String(300), nullable=False),
        sa.Column('start_date',    sa.Date(),      nullable=False),
        sa.Column('end_date',      sa.Date(),      nullable=False),
        sa.Column('created_by_id', sa.Integer(),   sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at',    sa.DateTime(),  nullable=False),
    )
    op.create_index('ix_holidays_start_date', 'holidays', ['start_date'])
    op.create_index('ix_holidays_end_date', 'holidays', ['end_date'])

    op.create_table(
        'homeworks',
        sa.Column('id',             sa.Integer(),   primary_key=True),
        sa.Column('group_id',       sa.Integer(),   sa.ForeignKey('groups.id'), nullable=False),
        sa.Column('lesson_id',      sa.Integer(),   sa.ForeignKey('lessons.id'), nullable=True),
        sa.Column('lesson_number',  sa.Integer(),   nullable=True),
        sa.Column('lesson_title',   sa.String(500), nullable=True),
        sa.Column('text',           sa.Text(),      nullable=False),
        sa.Column('lesson_date',    sa.Date(),      nullable=False),
        sa.Column('created_by_id',  sa.Integer(),   sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at',     sa.DateTime(),  nullable=False),
        sa.Column('telegram_sent',  sa.Boolean(),   nullable=False, server_default=sa.false()),
        sa.Column('telegram_error', sa.String(500), nullable=True),
    )
    op.create_index('ix_homeworks_group_id', 'homeworks', ['group_id'])
    op.create_index('ix_homeworks_lesson_date', 'homeworks', ['lesson_date'])

    op.add_column('groups', sa.Column('telegram_chat_id', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('groups', 'telegram_chat_id')
    op.drop_table('homeworks')
    op.drop_table('holidays')
