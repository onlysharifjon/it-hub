"""leads.phone_key + reminders.notified_at

Revision ID: 20260904_lead_phone_key
Revises:
Create Date: 2026-09-04
"""
import re

import sqlalchemy as sa
from alembic import op

revision = "20260904_lead_phone_key"
down_revision = "20260902b_certificates"
branch_labels = None
depends_on = None


def _key(phone):
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:] if len(digits) >= 9 else digits


def upgrade():
    op.add_column("leads", sa.Column("phone_key", sa.String(16), nullable=True))
    op.add_column("reminders", sa.Column("notified_at", sa.DateTime(), nullable=True))
    op.create_index("ix_leads_phone_key", "leads", ["phone_key"])
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, phone FROM leads")).fetchall()
    for lead_id, phone in rows:
        if phone and phone.startswith("no-phone-"):
            continue
        k = _key(phone)
        if k:
            conn.execute(
                sa.text("UPDATE leads SET phone_key = :k WHERE id = :i"),
                {"k": k, "i": lead_id},
            )


def downgrade():
    op.drop_column("reminders", "notified_at")
    op.drop_index("ix_leads_phone_key", table_name="leads")
    op.drop_column("leads", "phone_key")
