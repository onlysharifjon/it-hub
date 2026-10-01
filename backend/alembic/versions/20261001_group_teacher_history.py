"""group_teacher_history — guruh o'qituvchisi tarixi (maosh hisobi uchun).

Muammo: o'qituvchi maoshi guruhning HOZIRGI o'qituvchisiga (groups.teacher_id)
hisoblanardi — guruh boshqa o'qituvchiga o'tkazilsa, o'tgan oylardagi darslar
uchun ulush ham yangi o'qituvchiga o'tib ketardi (masalan S002: 2026-09-02 da
Ramazonbek → Sharifjon, avgust ulushi Sharifjonda ko'rinardi).

Mavjud guruhlar uchun tarix audit_logs'dagi teacher_id o'zgarishlaridan tiklanadi:
birinchi o'zgarishdagi eski o'qituvchi (yoki o'zgarish bo'lmasa — hozirgisi)
boshidan amal qiladi, keyin har bir o'zgarish yangi davr ochadi.

Revision ID: 20261001_group_teacher_history
Revises: 20260923_group_closed_at
Create Date: 2026-10-01
"""
import json
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = '20261001_group_teacher_history'
down_revision = '20260923_group_closed_at'
branch_labels = None
depends_on = None

EPOCH = datetime(2000, 1, 1)


def _tid(v):
    if v in (None, '', 'None', 'null'):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _load(v):
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    try:
        return json.loads(v)
    except ValueError:
        return {}


def upgrade() -> None:
    op.create_table(
        'group_teacher_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_group_teacher_history_id', 'group_teacher_history', ['id'])
    op.create_index('ix_group_teacher_history_group_id', 'group_teacher_history', ['group_id'])

    bind = op.get_bind()
    groups = bind.execute(sa.text("SELECT id, teacher_id FROM groups")).fetchall()
    audits = bind.execute(sa.text(
        "SELECT entity_id, changed_at, old_value, new_value FROM audit_logs "
        "WHERE entity_type = 'group' AND action = 'update' ORDER BY changed_at, id"
    )).fetchall()
    changes: dict = {}
    for gid, changed_at, old, new in audits:
        new_d = _load(new)
        if 'teacher_id' not in new_d:
            continue
        old_t, new_t = _tid(_load(old).get('teacher_id')), _tid(new_d.get('teacher_id'))
        if old_t != new_t:
            changes.setdefault(gid, []).append((changed_at, old_t, new_t))

    rows = []
    for gid, current in groups:
        ch = changes.get(gid, [])
        rows.append({'group_id': gid, 'teacher_id': ch[0][1] if ch else current, 'started_at': EPOCH})
        for changed_at, _old, new_t in ch:
            rows.append({'group_id': gid, 'teacher_id': new_t, 'started_at': changed_at})
        # Audit'ga tushmagan o'zgarish bo'lsa — hozirgi o'qituvchi shu paytdan
        if ch and ch[-1][2] != current:
            rows.append({'group_id': gid, 'teacher_id': current, 'started_at': datetime.utcnow()})
    if rows:
        bind.execute(sa.text(
            "INSERT INTO group_teacher_history (group_id, teacher_id, started_at, created_at) "
            "VALUES (:group_id, :teacher_id, :started_at, CURRENT_TIMESTAMP)"
        ), rows)


def downgrade() -> None:
    op.drop_index('ix_group_teacher_history_group_id', table_name='group_teacher_history')
    op.drop_index('ix_group_teacher_history_id', table_name='group_teacher_history')
    op.drop_table('group_teacher_history')
