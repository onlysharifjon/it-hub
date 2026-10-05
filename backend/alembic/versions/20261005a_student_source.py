"""students.source — talaba qayerdan kelgani (facebook | minar).

Mavjud talabalar: sentyabr 2026 da qo'shilganlar — facebook,
undan oldin qo'shilganlar — minar (Toshkent vaqti, UTC+5).

Revision ID: 20261005a_student_source
Revises: 20261002e_minar_qr_login
Create Date: 2026-10-05
"""
import sqlalchemy as sa
from alembic import op

revision = '20261005a_student_source'
down_revision = '20261002e_minar_qr_login'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('students') as b:
        b.add_column(sa.Column('source', sa.String(20), nullable=True))
    op.create_index('ix_students_source', 'students', ['source'])
    # created_at UTC'da saqlanadi: Toshkent 2026-09-01 00:00 = UTC 2026-08-31 19:00
    op.execute("UPDATE students SET source = 'minar' WHERE created_at < '2026-08-31 19:00:00'")
    op.execute("UPDATE students SET source = 'facebook' "
               "WHERE created_at >= '2026-08-31 19:00:00' AND created_at < '2026-09-30 19:00:00'")


def downgrade() -> None:
    op.drop_index('ix_students_source', 'students')
    with op.batch_alter_table('students') as b:
        b.drop_column('source')
