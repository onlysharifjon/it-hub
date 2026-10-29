"""Record the authorized coin reset without deleting financial history."""
from alembic import op
import sqlalchemy as sa

revision = '20261029a_coin_launch'
down_revision = '20261024b_exam_warnings'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('coin_launch',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('reset_at', sa.DateTime(), nullable=False),
        sa.Column('launch_at', sa.DateTime(), nullable=False),
        sa.Column('keep_test_coins', sa.Boolean(), nullable=False),
        sa.Column('balance_snapshot', sa.Text(), nullable=False),
        sa.CheckConstraint('id = 1', name='ck_coin_launch_singleton'))


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM coin_launch')).scalar():
        raise RuntimeError('Coin reset is active. Removing it would restore old balances; explicit recovery is required.')
    op.drop_table('coin_launch')
