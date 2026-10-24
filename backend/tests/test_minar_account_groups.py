"""SPACE account provisioning through staff and teacher group selectors."""
from datetime import datetime, timedelta
from backend import models
from backend.minar.models import MinarAccount
from backend.tests.conftest import _create_user, _login
from backend.tests.test_minar import _minar_env, H, make_student, new_account, login


def test_support_teacher_selector_returns_all_active_groups(client, db, metodist_token, teacher_token, teacher_user):
    groups = [models.Group(name=f'Group {i:03}', is_active=True) for i in range(105)]
    groups[0].teacher_id = teacher_user.id
    archived = models.Group(name='Closed group', is_active=False, teacher_id=teacher_user.id)
    db.add_all([*groups, archived]); db.commit()
    # The old UI request was rejected before it could render any options.
    assert client.get('/groups?is_active=true&page_size=200', headers=H(metodist_token)).status_code == 422
    response = client.get('/space/admin/account-groups', headers=H(metodist_token))
    assert response.status_code == 200
    assert len(response.json()) == 105
    assert response.json() == [{'id': g.id, 'name': g.name} for g in groups]
    own = client.get('/space/admin/account-groups', headers=H(teacher_token)).json()
    assert own == [{'id': groups[0].id, 'name': groups[0].name}]
    assert client.get('/space/admin/account-groups').status_code == 401
    hunter = _create_user(db, 'account-hunter', 'test-password', models.UserRole.hunter)
    token = _login(client, hunter.username, 'test-password')
    assert client.get('/space/admin/account-groups', headers=H(token)).status_code == 403
    admin = _create_user(db, 'account-admin', 'test-password', models.UserRole.admin)
    token = _login(client, admin.username, 'test-password')
    assert len(client.get('/space/admin/account-groups', headers=H(token)).json()) == 105


def test_teacher_bulk_creates_working_credentials_only_for_own_active_members(client, db, teacher_user, teacher_token, metodist_token):
    first, group = make_student(db, 'New Student One')
    group.teacher_id = teacher_user.id; db.commit()
    second, _ = make_student(db, 'New Student Two', group=group)
    existing, credentials = new_account(client, db, metodist_token, 'Existing Student', group=group)
    original_hash = db.query(MinarAccount).filter_by(student_id=existing.id).one().password_hash
    left, _ = make_student(db, 'Left Member', group=group)
    membership = db.query(models.GroupStudent).filter_by(student_id=left.id, group_id=group.id).one()
    membership.left_at = datetime.utcnow()
    archived, _ = make_student(db, 'Archived Member', group=group); archived.is_archived = True
    inactive, _ = make_student(db, 'Inactive Member', group=group); inactive.is_active = False
    outsider, other = make_student(db, 'Other Teacher Student')
    db.commit()
    path = '/space/admin/accounts/bulk'
    assert client.post(path, headers=H(teacher_token), json={'group_id': other.id}).status_code == 403
    assert client.post(path, json={'group_id': group.id}).status_code == 401
    response = client.post(path, headers=H(teacher_token), json={'group_id': group.id})
    assert response.status_code == 201, response.text
    created = response.json()['created']
    assert response.json()['count'] == 2
    assert {c['student_id'] for c in created} == {first.id, second.id}
    for item in created:
        assert item['group'] == group.name and item['login_id'].startswith('MA') and len(item['password']) == 8
        assert login(client, item).status_code == 200
    assert login(client, credentials).status_code == 200
    again = client.post(path, headers=H(teacher_token), json={'group_id': group.id})
    assert again.status_code == 201 and again.json()['count'] == 0
    db.expire_all()
    assert db.query(MinarAccount).filter_by(student_id=existing.id).one().password_hash == original_hash
    assert db.query(MinarAccount).count() == 3
    # Creating accounts does not grant unrelated account administration rights.
    assert client.post(f'/space/admin/accounts/{first.id}/reset-password', headers=H(teacher_token)).status_code == 403
    assert client.patch(f'/space/admin/accounts/{first.id}', headers=H(teacher_token), json={'is_active': False}).status_code == 403
    assert client.post('/space/admin/accounts/qr', headers=H(teacher_token), json={'group_id': group.id}).status_code == 403
    group = db.get(models.Group, group.id); group.is_active = False; db.commit()
    assert client.post(path, headers=H(teacher_token), json={'group_id': group.id}).status_code == 400


def test_teacher_account_listing_does_not_leak_other_groups_and_revokes_after_reassignment(client, db, teacher_user, teacher_token, metodist_token):
    own, credentials = new_account(client, db, metodist_token, 'Shared Student')
    group = db.query(models.Group).first(); group.teacher_id = teacher_user.id
    other_student, _ = new_account(client, db, metodist_token, 'Foreign Student')
    other = db.query(models.Group).filter(models.Group.id != group.id).one()
    other.name = 'Foreign group'
    db.add(models.GroupStudent(group_id=other.id, student_id=own.id, joined_at=datetime.utcnow()+timedelta(seconds=1)))
    db.commit()
    response = client.get('/space/admin/accounts', headers=H(teacher_token))
    assert response.status_code == 200
    assert [item['student_id'] for item in response.json()] == [own.id]
    assert response.json()[0]['group'] == group.name
    assert 'password' not in response.json()[0]
    assert client.get(f'/space/admin/accounts?group_id={other.id}', headers=H(teacher_token)).status_code == 403
    assert client.get('/space/admin/accounts?q=Foreign', headers=H(teacher_token)).json() == []
    assert len(client.get('/space/admin/accounts', headers=H(metodist_token)).json()) == 2
    membership = db.query(models.GroupStudent).filter_by(group_id=group.id, student_id=own.id).one()
    membership.left_at = datetime.utcnow(); db.commit()
    assert client.get('/space/admin/accounts', headers=H(teacher_token)).json() == []
    membership.left_at = None
    group.teacher_id = None; db.commit()
    assert client.get('/space/admin/account-groups', headers=H(teacher_token)).json() == []
    assert client.get('/space/admin/accounts', headers=H(teacher_token)).json() == []
    assert client.post('/space/admin/accounts/bulk', headers=H(teacher_token), json={'group_id': group.id}).status_code == 403
