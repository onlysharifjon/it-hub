"""Teacher/group allocations, access scope and real PostgreSQL writer races."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy import event, text
from backend import models, tz
from backend.main import _award_coins, save_attendance
from backend.reward_policy import budgets, student_used, teacher_budget
from backend.tests.test_reward_policy import classroom
from backend.tests.conftest import _create_user, _login, TestSessionLocal


def headers(client, name):
    return {'Authorization': 'Bearer ' + _login(client, name, 'pass123')}


def test_group_budgets_scoped_and_unique_students(client, db, classroom):
    teacher, student, group = classroom
    other = _create_user(db, 'other-budget', 'pass123', models.UserRole.teacher)
    admin = _create_user(db, 'admin-budget', 'pass123', models.UserRole.admin)
    second = models.Group(name='Second own group', teacher_id=teacher.id)
    foreign = models.Group(name='Foreign group', teacher_id=other.id)
    db.add_all([second, foreign]); db.flush()
    db.add_all([models.GroupStudent(group_id=g.id, student_id=student.id) for g in [second, foreign]])
    db.commit()
    _award_coins(db, other, student_id=student.id, group_id=foreign.id, amount=60, reason='Test'); db.commit()
    response = client.get('/coins/budgets', headers=headers(client, 'coin-teacher'))
    assert response.status_code == 200
    rows = response.json()
    assert {r['id'] for r in rows} == {group.id, second.id}
    assert all(r['teacher_budget'] == 70 and r['teacher_students'] == 1 for r in rows)
    assert all(r['budget'] == 70 and r['available'] == 10 and r['teacher_available'] == 10 for r in rows)
    assert all(r['students'][0]['used'] == 60 for r in rows)
    assert len(client.get('/coins/budgets', headers=headers(client, 'admin-budget')).json()) == 3
    assert client.get('/coins/budgets').status_code in (401, 403)


def test_inactive_students_and_departed_members_do_not_allocate(db, classroom):
    teacher, student, group = classroom
    for idx, (active, archived, departed) in enumerate([(False, False, False), (True, True, False), (True, False, True)]):
        st = models.Student(full_name=f'Excluded {idx}', phone1='000', is_active=active, is_archived=archived)
        db.add(st); db.flush()
        db.add(models.GroupStudent(student_id=st.id, group_id=group.id, left_at=tz.utcnow() if departed else None))
    db.commit()
    assert teacher_budget(db, teacher.id) == 70
    assert [s['id'] for s in budgets(db, teacher)[0]['students']] == [student.id]


def test_budget_reads_are_batched(db, classroom):
    teacher, _, _ = classroom
    for i in range(20):
        group = models.Group(name=f'Group {i}', teacher_id=teacher.id)
        student = models.Student(full_name=f'Student {i}', phone1='000')
        db.add_all([group, student]); db.flush()
        db.add(models.GroupStudent(group_id=group.id, student_id=student.id))
    db.commit()
    teacher_id = teacher.id  # materialize expired ORM attributes before counting SQL
    queries = []
    def record(*args): queries.append(args[2])
    event.listen(db.bind, 'before_cursor_execute', record)
    try:
        rows = budgets(db, teacher)
    finally:
        event.remove(db.bind, 'before_cursor_execute', record)
    assert len(rows) == 21
    assert len(queries) <= 11  # fixed number of queries, including reset-epoch lookups


def test_api_student_cap_survives_cancellation(client, db, classroom):
    teacher, student, group = classroom
    h = headers(client, 'coin-teacher')
    payload = {'student_id': student.id, 'group_id': group.id, 'amount': 70, 'reason': 'Uy vazifasi'}
    first = client.post('/coins/give', headers=h, json=payload)
    assert first.status_code == 201, first.text
    assert client.delete(f"/coins/transactions/{first.json()['id']}", headers=h).status_code == 204
    payload['amount'] = 1
    denied = client.post('/coins/give', headers=h, json=payload)
    assert denied.status_code == 400 and '70' in denied.json()['detail']
    assert client.get('/coins/budgets', headers=h).json()[0]['available'] == 0


def test_postgres_concurrent_teachers_share_student_cap(db, classroom):
    if db.bind.dialect.name != 'postgresql': pytest.skip('Requires isolated PostgreSQL test database')
    teacher, student, group = classroom
    other = _create_user(db, 'race-teacher', 'pass123', models.UserRole.teacher)
    second = models.Group(name='Other race group', teacher_id=other.id)
    db.add(second); db.flush(); db.add(models.GroupStudent(group_id=second.id, student_id=student.id)); db.commit()
    _award_coins(db, teacher, student_id=student.id, group_id=group.id, amount=69, reason='Test'); db.commit()
    sid = student.id
    actors = [(teacher.id, group.id), (other.id, second.id)]
    barrier = Barrier(2)
    def grant(pair):
        with TestSessionLocal() as session:
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            actor = session.get(models.User, pair[0])
            barrier.wait(timeout=5)
            try:
                _award_coins(session, actor, student_id=sid, group_id=pair[1], amount=1, reason='Race')
                session.commit()
                return 'granted'
            except HTTPException as error:
                session.rollback()
                assert error.status_code == 400
                return 'capped'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(grant, actors)) == ['capped', 'granted']
    db.expire_all()
    assert student_used(db, sid) == 70


def test_postgres_overlapping_attendance_batches_do_not_deadlock(db, classroom):
    if db.bind.dialect.name != 'postgresql': pytest.skip('Requires isolated PostgreSQL test database')
    teacher, student, group = classroom
    other = _create_user(db, 'race-attendance', 'pass123', models.UserRole.teacher)
    second = models.Group(name='Other attendance group', teacher_id=other.id)
    st2 = models.Student(full_name='Second student', phone1='000')
    db.add_all([second, st2]); db.flush()
    db.add_all([models.GroupStudent(group_id=group.id, student_id=st2.id),
                models.GroupStudent(group_id=second.id, student_id=student.id),
                models.GroupStudent(group_id=second.id, student_id=st2.id)])
    db.commit()
    ids = [student.id, st2.id]
    actors = [(teacher.id, group.id, ids), (other.id, second.id, list(reversed(ids)))]
    barrier = Barrier(2)
    def attend(args):
        with TestSessionLocal() as session:
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            actor = session.get(models.User, args[0])
            barrier.wait(timeout=5)
            return save_attendance(args[1], tz.today().isoformat(),
                                   [{'student_id': sid, 'is_present': True} for sid in args[2]], session, actor)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert all(r['saved'] == 2 for r in pool.map(attend, actors))
    db.expire_all()
    assert all(student_used(db, sid) == 2 for sid in ids)

@pytest.mark.parametrize('amount', [1.5, True, '7', 0, 71])
def test_api_rejects_invalid_coin_amounts(client, classroom, amount):
    teacher, student, group = classroom
    response = client.post('/coins/give', headers=headers(client, 'coin-teacher'),
                           json={'student_id': student.id, 'group_id': group.id, 'amount': amount})
    assert response.status_code == 422


def test_attendance_coin_must_be_reversed_from_attendance(client, db, classroom):
    teacher, student, group = classroom
    save_attendance(group.id, tz.today().isoformat(), [{'student_id': student.id, 'is_present': True}], db, teacher)
    listing = client.get('/coins/transactions', headers=headers(client, 'coin-teacher')).json()
    assert listing[0]['automatic'] is True and listing[0]['reason'].startswith('Davomat uchun coin')
    tx = db.query(models.CoinTransaction).one()
    response = client.delete(f'/coins/transactions/{tx.id}', headers=headers(client, 'coin-teacher'))
    assert response.status_code == 400 and 'yo‘qlama' in response.json()['detail']
    save_attendance(group.id, tz.today().isoformat(), [{'student_id': student.id, 'is_present': False}], db, teacher)
    assert sum(t.amount for t in db.query(models.CoinTransaction)) == 0


def test_manual_restart_restores_full_monthly_allowance(db, classroom):
    from datetime import datetime, timedelta
    from backend import models
    from backend.reward_policy import student_used, budgets, validate_grant
    from backend.main import _coins_spent_this_month
    from backend.minar.models import MinarAccount, MinarLedger
    teacher, student, group = classroom
    now = datetime.utcnow()
    db.add(models.CoinTransaction(student_id=student.id, teacher_id=teacher.id, group_id=group.id, amount=70, created_at=now-timedelta(minutes=1)))
    account = MinarAccount(student_id=student.id, login_id='RESET1', password_hash='unused')
    db.add(account); db.flush()
    db.add(MinarLedger(account_id=account.id, ref_key='old-game', kind='game', title='Old game', amount=10, local_date=now.date().isoformat(), created_at=now-timedelta(minutes=1)))
    db.add(models.CoinLaunch(id=1, reset_at=now, launch_at=now, keep_test_coins=False, balance_snapshot='{}'))
    db.commit()
    assert student_used(db, student.id) == 0
    row = budgets(db, teacher)[0]
    assert row['used'] == row['teacher_used'] == 0 and row['students'][0]['remaining'] == 70
    assert _coins_spent_this_month(db, teacher.id) == 0
    validate_grant(db, teacher, student.id, group.id, 70)
