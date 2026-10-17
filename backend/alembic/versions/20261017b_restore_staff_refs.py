"""Preserve historical staff references using explicitly inactive archive records.

A restore rehearsal found legacy rows referencing previously removed users.
No history is deleted or attributed to an existing person. Archive accounts have
random unknown passwords, no contact information, no salary and cannot log in.
"""
from alembic import op
import sqlalchemy as sa
import bcrypt
import secrets

revision = '20261017b_restore_staff_refs'
down_revision = '20261017a_space_audit'
branch_labels = None
depends_on = None


def upgrade():
    db = op.get_bind()
    missing = db.execute(sa.text('''
        SELECT DISTINCT changed_by_id AS id FROM audit_logs a
        WHERE changed_by_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id=a.changed_by_id)
        UNION
        SELECT DISTINCT issued_by_id AS id FROM staff_warnings w
        WHERE issued_by_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id=w.issued_by_id)
    ''')).scalars().all()
    for uid in missing:
        db.execute(sa.text('''INSERT INTO users
            (id, username, hashed_password, full_name, role, is_active, salary_exempt, blocked_reason, created_at)
            VALUES (:id, :username, :password, :name, 'teacher', false, true, :reason, CURRENT_TIMESTAMP)'''),
            {'id':uid, 'username':f'__archive_{uid}_{secrets.token_hex(6)}',
             'password':bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt()).decode(),
             'name':f'Arxiv yozuvi #{uid}',
             'reason':'SPACE audit: avval o‘chirilgan xodimga bog‘langan tarixni saqlash uchun yaratilgan. Shaxs va asl rol noma’lum. Login taqiqlangan; faollashtirmang.'})
    if missing and db.dialect.name == 'postgresql':
        db.execute(sa.text("SELECT setval(pg_get_serial_sequence('users','id'), greatest(nextval(pg_get_serial_sequence('users','id')), (SELECT max(id) FROM users)), true)"))


def downgrade():
    # Removing these archive records would break or delete historical records.
    pass
