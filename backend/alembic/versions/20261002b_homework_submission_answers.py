"""homework_submissions: Space javobi (answer, link) va baholash (graded_at, graded_by_id, coins).

Revision ID: 20261002b_hw_answers
Revises: 20261002a_minar_notif_ach
Create Date: 2026-10-02
"""
import sqlalchemy as sa
from alembic import op

revision = '20261002b_hw_answers'
down_revision = '20261002a_minar_notif_ach'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('homework_submissions') as b:
        b.add_column(sa.Column('answer', sa.Text(), nullable=True))
        b.add_column(sa.Column('link', sa.String(500), nullable=True))
        b.add_column(sa.Column('graded_at', sa.DateTime(), nullable=True))
        b.add_column(sa.Column('graded_by_id', sa.Integer(), sa.ForeignKey('users.id', name='fk_hw_sub_graded_by'),
                               nullable=True))
        b.add_column(sa.Column('coins', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('homework_submissions') as b:
        b.drop_column('coins')
        b.drop_column('graded_by_id')
        b.drop_column('graded_at')
        b.drop_column('link')
        b.drop_column('answer')
