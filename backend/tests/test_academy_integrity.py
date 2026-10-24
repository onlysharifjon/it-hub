"""Browser warning persistence, scoped review and unchanged scoring."""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path
import pytest
from backend.minar.academy_models import AcademyAttempt
from backend.tests.test_minar import acct, _minar_env, H, post, new_account, login
from backend.tests.test_space_academy import provision, start, correct_answers, admin_token, admin_user


def event(kind, n=1):
    return {'id': f'warning-event-{n}', 'type': kind}


def test_warnings_retry_review_and_score(client, db, acct, admin_token, teacher_token, metodist_token):
    _, assignment = provision(client, db, admin_token, dueAt=None)
    attempt = start(client, assignment); path = '/academy/attempts/' + attempt['id']
    assert attempt['integrityEvents'] == []
    events = [event('window_leave'), event('copy', 2), event('paste', 3)]
    for _ in range(2):
        r = post(client, path, {'integrityEvents': events}); assert r.status_code == 200, r.text
        assert r.json()['warnings'] == 3 and not r.json()['finishedAt']
    assert all(datetime.fromisoformat(e['recordedAt']).utcoffset() == timedelta(0) for e in r.json()['integrityEvents'])
    # Resume and empty/legacy updates cannot erase or duplicate the server history.
    assert start(client, assignment)['integrityEvents'] == r.json()['integrityEvents']
    assert post(client, path, {'warnings': 0, 'integrityEvents': []}).json()['warnings'] == 3
    report = client.get('/space/admin/academy/report', headers=H(metodist_token)).json()['attempts'][0]
    assert report['integrity']['counts'] == {'window_leave': 1, 'copy': 1, 'paste': 1}
    detail = client.get('/space/admin' + path, headers=H(metodist_token))
    assert detail.status_code == 200 and len(detail.json()['integrityEvents']) == 3
    assert client.get('/space/admin' + path, headers=H(teacher_token)).status_code == 404
    correct = correct_answers(db, attempt['id'])
    finished = post(client, path, {'answers': correct, 'integrityEvents': events, 'submit': True}).json()
    assert finished['score'] == 100 and finished['warnings'] == 3
    late = post(client, path, {'integrityEvents': [event('print', 4)]}).json()
    assert late['warnings'] == 3 and late['score'] == 100
    _, credentials = new_account(client, db, metodist_token, name='No access to warning history')
    login(client, credentials)
    assert client.get('/space' + path).status_code == 404
    assert post(client, path, {'integrityEvents': events}).status_code == 404


@pytest.mark.parametrize('payload', [
    {'integrityEvents': {}},
    {'integrityEvents': [event('screen_recording')]},
    {'integrityEvents': [{'id': 'short', 'type': 'copy'}]},
    {'integrityEvents': [{'id': 'valid-id-123', 'type': ['copy']}]},
    {'integrityEvents': [{**event('copy'), 'clipboard': 'must not be stored'}]},
    {'integrityEvents': [event('copy', i) for i in range(201)]},
])
def test_invalid_warning_payload_is_atomic(client, db, acct, admin_token, payload):
    _, assignment = provision(client, db, admin_token)
    attempt = start(client, assignment)
    r = post(client, '/academy/attempts/' + attempt['id'], {**payload, 'answers': correct_answers(db, attempt['id'])})
    assert r.status_code == 400, r.text
    db.expire_all(); row = db.get(AcademyAttempt, attempt['id'])
    assert row.answers == '{}' and row.integrity_events == '[]' and row.warnings == 0


def test_warning_limit_and_legacy_counts(client, db, acct, admin_token):
    _, assignment = provision(client, db, admin_token); attempt = start(client, assignment)
    path = '/academy/attempts/' + attempt['id']
    assert post(client, path, {'warnings': 2}).json()['integrity']['legacyWarnings'] == 2
    batch = [event('copy', i) for i in range(200)]
    assert post(client, path, {'integrityEvents': batch}).json()['warnings'] == 202
    limited = post(client, path, {'integrityEvents': [event('paste', 201)]}).json()
    assert limited['warnings'] == 202 and len(limited['integrityEvents']) == 200
    assert limited['integrity']['limitReached'] and limited['integrity']['legacyWarnings'] == 2
    assert post(client, path, {'integrityEvents': batch, 'submit': True}).json()['warnings'] == 202


def test_public_warning_cookie_binding_and_manual_closure(client, db, acct, admin_token, metodist_token):
    _, assignment = provision(client, db, admin_token, public=True, dueAt=None)
    base = '/space/academy/public/' + assignment['publicToken']
    attempt = client.post(base + '/start', json={'name': 'Warning Test', 'phone': '998901234567', 'consent': True}).json()
    path = base + '/attempts/' + attempt['id']
    response = client.post(path, json={'integrityEvents': [event('fullscreen_exit')]})
    assert response.status_code == 200 and response.json()['warnings'] == 1
    assert client.post(f'/space/admin/academy/assignments/{assignment["id"]}/status', headers=H(metodist_token), json={'active': False}).status_code == 200
    closed = client.post(path, json={}).json()
    assert closed['finishedAt'] and closed['warnings'] == 1
    client.cookies.clear()
    assert client.post(path, json={'integrityEvents': [event('copy', 2)]}).status_code == 404


def test_warning_migration_preserves_existing_scores_and_history(tmp_path):
    from sqlalchemy import create_engine, text, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    module_path = Path(__file__).parents[1] / 'alembic/versions/20261024b_exam_warnings.py'
    spec = importlib.util.spec_from_file_location('warning_migration', module_path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = create_engine('sqlite:///' + str(tmp_path / 'warnings.sqlite'))
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE minar_academy_attempts (id TEXT PRIMARY KEY, warnings INTEGER NOT NULL, score INTEGER)'))
        connection.execute(text("INSERT INTO minar_academy_attempts VALUES ('old', 4, 80)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        row = connection.execute(text('SELECT warnings, score, integrity_events FROM minar_academy_attempts')).one()
        assert tuple(row) == (4, 80, '[]')
        connection.execute(text('UPDATE minar_academy_attempts SET integrity_events=:events'), {'events': json.dumps([event('copy')])})
        with pytest.raises(RuntimeError, match='Warning history exists'): migration.downgrade()
        connection.execute(text("UPDATE minar_academy_attempts SET integrity_events='[]'"))
        migration.downgrade()
        assert 'integrity_events' not in {c['name'] for c in inspect(connection).get_columns('minar_academy_attempts')}
        assert tuple(connection.execute(text('SELECT warnings, score FROM minar_academy_attempts')).one()) == (4, 80)
    engine.dispose()
