"""groups.closed_at — guruh arxivlangan sana.

Muammo: arxivlangan (is_active=False) guruh qarz hisobidan (core_calc.student_cumulative_owed)
butunlay tushib qolardi — talabaning o'sha guruhdagi o'tgan oylari "unutilib", shu oylar
uchun qilingan to'lovlar boshqa oylar qarzini yopib yuborardi (masalan S007 → S003 ga
o'tgan talabaning avgust to'lovi sentyabr qarzini yopgan).

Endi arxivlangan guruh `closed_at` oyigacha hisoblanadi. Mavjud arxivlangan guruhlar
uchun sana audit_logs'dagi oxirgi "is_active → False" yozuvidan olinadi.

Revision ID: 20260923_group_closed_at
Revises: 20260922_group_student_left_at
Create Date: 2026-09-23
"""
import sqlalchemy as sa
from alembic import op

revision = '20260923_group_closed_at'
down_revision = '20260922_group_student_left_at'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('groups', sa.Column('closed_at', sa.DateTime(), nullable=True))
    op.execute("""
        UPDATE groups SET closed_at = (
            SELECT MAX(a.changed_at) FROM audit_logs a
            WHERE a.entity_type = 'group' AND a.entity_id = groups.id
              AND a.action = 'update' AND a.new_value LIKE '%"is_active": "False"%'
        )
        WHERE is_active = false
    """)


def downgrade() -> None:
    op.drop_column('groups', 'closed_at')
