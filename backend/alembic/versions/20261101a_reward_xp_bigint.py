"""Allow exponential level thresholds beyond the 32-bit XP ceiling."""
from alembic import op
import sqlalchemy as sa

revision = '20261101a_reward_xp_bigint'
down_revision = '20261029a_coin_launch'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('minar_accounts') as batch:
        batch.alter_column('xp', existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=False)


def downgrade():
    # Refuse a lossy rollback once students exceed the previous storage range.
    bind=op.get_bind()
    if bind.execute(sa.text('SELECT COUNT(*) FROM minar_accounts WHERE xp > 2147483647')).scalar():
        raise RuntimeError('XP exceeds the old integer range; keep the BigInteger column.')
    with op.batch_alter_table('minar_accounts') as batch:
        batch.alter_column('xp', existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=False)
