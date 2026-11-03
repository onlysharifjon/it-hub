"""Retire unassigned coding drills and expand the authored Foundation checks."""
from alembic import op
import json
import sqlalchemy as sa
from datetime import datetime

revision = '20261103a_group_learning'
down_revision = '20261102a_social_rooms'
branch_labels = None
depends_on = None


def upgrade():
    from backend.minar.foundation_checks import additions
    conn = op.get_bind()
    # Keep historical assessment references; retired materials cannot be opened.
    conn.execute(sa.text("UPDATE minar_content SET published=false WHERE lesson_id IS NULL AND course IN ('HTML','CSS','JavaScript')"))
    rows = conn.execute(sa.text("SELECT c.id,c.slug,c.questions,l.lesson_number FROM minar_content c JOIN lessons l ON l.id=c.lesson_id WHERE l.category='foundation' AND c.updated_by_id IS NULL")).mappings()
    for row in rows:
        n = row['lesson_number']
        if n not in range(1,25) or row['slug'] != f'foundation-{n}':
            continue
        old = json.loads(row['questions'])
        if len(old) != 1:
            continue
        conn.execute(sa.text('UPDATE minar_content SET questions=:questions,updated_at=:now WHERE id=:id'),
            {'questions':json.dumps(old + additions(n), ensure_ascii=False), 'now':datetime.utcnow(), 'id':row['id']})


def downgrade():
    # Content remains authored and historical attempts stay valid on code rollback.
    pass
