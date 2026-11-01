"""Planet purchases are atomic wallet operations and profiles expose only public data."""
import json
import uuid
import pytest
from backend import models
from backend.minar import service, catalog as C
from backend.minar.models import MinarAccount, MinarPurchase
from backend.tests.test_minar import acct, _minar_env, post, give_coins


def test_every_planet_auto_selects_and_uses_server_price(client, db, acct, metodist_user):
    st, _ = acct
    give_coins(db, st, 2000, metodist_user.id)
    balance = 2000
    assert len(C.PLANETS) == 7
    for pid, (name, price) in C.PLANETS.items():
        payload = {'productId': pid, 'requestId': str(uuid.uuid4()), 'price': 0}
        response = post(client, '/shop/purchases', payload)
        assert response.status_code == 200, response.text
        state = response.json()['state']
        balance -= price
        assert state['balance'] == balance
        assert state['equipment']['planet'] == pid
        assert state['xp'] == 0 and state['lightning'] == 0
        assert pid in state['owned']
        assert client.get('/space/students/me/bootstrap').json()['equipment']['planet'] == pid
        replay = post(client, '/shop/purchases', payload).json()['state']
        assert replay['balance'] == balance
        assert post(client, '/shop/purchases', {**payload, 'requestId': str(uuid.uuid4())}).status_code == 409
    assert db.query(MinarPurchase).count() == 7
    assert client.get('/space/profiles/'+acct[1]['login_id']).json()['equipment']['planet'] == 'planet-celestia'


def test_failed_purchase_does_not_change_wallet_or_planet(client, db, acct, metodist_user):
    st, _ = acct
    give_coins(db, st, 35, metodist_user.id)
    first = {'productId': 'planet-verdora', 'requestId': 'planet-intent-first'}
    assert post(client, '/shop/purchases', first).status_code == 200
    before = client.get('/space/students/me/bootstrap').json()
    assert post(client, '/shop/purchases', {**first, 'productId': 'planet-pyron'}).status_code == 409
    assert post(client, '/shop/purchases', {'productId': 'planet-pyron', 'requestId': 'planet-intent-second'}).status_code == 400
    assert post(client, '/avatar/equipment', {'productId': 'planet-pyron'}).status_code == 400
    after = client.get('/space/students/me/bootstrap').json()
    for key in ('balance','xp','equipment','purchases','owned'):
        assert before[key] == after[key]


def test_planet_owner_outside_podium_has_public_profile(client, db, acct, metodist_user):
    me = db.query(MinarAccount).one()
    others = []
    for i in range(5):
        st = models.Student(full_name=f'Explorer Secret{i}', phone1='+998901111111', is_active=True, is_archived=False)
        db.add(st); db.flush()
        acc = MinarAccount(student_id=st.id, login_id=f'WORLD{i}', password_hash='private', xp=i*2000,
                           is_active=True, is_test=False, course='HTML')
        db.add(acc); db.flush(); others.append(acc)
    db.commit()
    other = others[0]
    url = '/space/profiles/'+other.login_id
    assert client.get(url).status_code == 404
    # A forged selection without a purchase does not publish a profile.
    other.equipment = json.dumps({'planet':'planet-glacia'})
    db.commit()
    assert client.get(url).status_code == 404
    give_coins(db, db.get(models.Student, other.student_id), 120, metodist_user.id)
    service.run(db, other, service.act_purchase, 'planet-glacia', 'planet-public-intent')
    response = client.get(url)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['equipment']['planet'] == 'planet-glacia'
    assert data['name'] == 'Explorer S.' and 'Secret0' not in response.text
    assert set(data) == {'id','name','course','character','level','xp','lightning','coins','badges','equipment'}
    for attr in ('is_test',):
        setattr(other, attr, True); db.commit()
        assert client.get(url).status_code == 404
        setattr(other, attr, False); db.commit()
    other.is_active = False; db.commit()
    assert client.get(url).status_code == 404
    other.is_active = True; db.commit()
    student = db.get(models.Student, other.student_id)
    student.is_archived = True; db.commit()
    assert client.get(url).status_code == 404
    student.is_archived = False; student.is_active = False; db.commit()
    assert client.get(url).status_code == 404
    client.cookies.clear()
    assert client.get('/space/profiles/'+me.login_id).status_code == 401


def test_legacy_purchases_remain_and_retry_is_safe(client, db, acct):
    acc = db.query(MinarAccount).one()
    db.add(MinarPurchase(id=str(uuid.uuid4()),account_id=acc.id,request_id='legacy-intent-001',
        product_id='cap',name='Dasturchi kepkasi',price=65,status='delivered',local_date='2026-10-01'))
    db.commit()
    result = post(client,'/shop/purchases',{'productId':'cap','requestId':'legacy-intent-001'})
    assert result.status_code == 200
    assert result.json()['state']['owned'] == ['cap']
    assert post(client,'/shop/purchases',{'productId':'cap','requestId':'legacy-intent-new'}).status_code == 410


@pytest.mark.parametrize('equipment', ['[]','null','"bad"','{bad','{"planet":"cap"}'])
def test_malformed_equipment_is_safe(equipment):
    acc = MinarAccount(equipment=equipment)
    assert service.get_equipment(acc)['planet'] is None


def test_postgres_same_planet_parallel_requests_charge_once(client, db, acct, metodist_user):
    if db.bind.dialect.name != 'postgresql': pytest.skip('PostgreSQL row locks required')
    from concurrent.futures import ThreadPoolExecutor
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.tests.test_minar import login
    st, creds = acct
    give_coins(db, st, 500, metodist_user.id)
    clients = [TestClient(app), TestClient(app)]
    for c in clients: login(c, creds)
    def buy(c): return c.post('/space/shop/purchases',json={'productId':'planet-aurelia','requestId':str(uuid.uuid4())}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool: codes = list(pool.map(buy, clients))
    assert sorted(codes) == [200,409]
    db.expire_all()
    assert service.balance_and_earned(db, db.query(MinarAccount).one())[0] == 340
    assert db.query(MinarPurchase).count() == 1
