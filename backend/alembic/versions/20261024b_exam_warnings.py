"""Keep bounded, typed browser warnings for assessment review."""
from alembic import op
import sqlalchemy as sa

revision = '20261024b_exam_warnings'
down_revision = '20261024a_manual_test_close'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('minar_academy_attempts', sa.Column(
        'integrity_events', sa.Text(), nullable=False, server_default='[]'))


def downgrade():
    # Application rollback keeps this additive column and its evidence intact.
    count = op.get_bind().execute(sa.text(
        "SELECT count(*) FROM minar_academy_attempts WHERE integrity_events != '[]'"
    )).scalar()
    if count:
        raise RuntimeError('Warning history exists. Export it before explicitly removing this column.')
    with op.batch_alter_table('minar_academy_attempts') as batch:
        batch.drop_column('integrity_events')
