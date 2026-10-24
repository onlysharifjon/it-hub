"""Allow assessments to remain open until a teacher ends them."""
from alembic import op
import sqlalchemy as sa

revision = '20261024a_manual_test_close'
down_revision = '20261022a_academy'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('minar_academy_assignments') as batch:
        batch.alter_column('due_at', existing_type=sa.DateTime(), nullable=True)


def downgrade():
    # Do not invent a closing time or delete open-ended assessments on rollback.
    count = op.get_bind().execute(sa.text(
        'SELECT count(*) FROM minar_academy_assignments WHERE due_at IS NULL'
    )).scalar()
    if count:
        raise RuntimeError('Open-ended tests exist. Set explicit deadlines before downgrading this schema.')
    with op.batch_alter_table('minar_academy_assignments') as batch:
        batch.alter_column('due_at', existing_type=sa.DateTime(), nullable=False)
