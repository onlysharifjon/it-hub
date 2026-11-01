"""Reset and temporary coins use the same accounting in SPACE, CRM and parent API."""
import json
from datetime import datetime, timedelta
import pytest
from backend import models, coin_launch
from backend.wallet import balance
from backend.minar import service, catalog as C
from backend.minar.models import MinarAccount, MinarLedger, MinarStock, MinarPurchase
from backend.parent.service import build_coins
from backend.tests.test_minar import _minar_env, acct, give_coins, post, H, play_typing
from backend.tests.test_space_audit_release import admin_user, admin_token


def configure(db, monkeypatch, keep=True):
    now=datetime(2026,10,29,12)
    # Everything already in the fixture belongs to the previous wallet epoch.
    for model in (models.CoinTransaction, MinarLedger, MinarPurchase):
        db.query(model).update({model.created_at:now-timedelta(seconds=1)})
    db.commit()
    monkeypatch.setattr(coin_launch,'utcnow',lambda:now)
    coin_launch.reset_all(db,keep_test_coins=keep)
    db.commit()
    return now


def test_reset_all_students_preserves_history_and_is_idempotent(client,db,acct,admin_user,admin_token,monkeypatch):
    st,_=acct;acc=db.query(MinarAccount).one()
    other=models.Student(full_name='No SPACE account',phone1='+998900001111',is_active=False,is_archived=True)
    db.add(other);db.commit()
    give_coins(db,st,100,admin_user.id)
    give_coins(db,other,77,admin_user.id)
    old=MinarLedger(account_id=acc.id,ref_key='old-credit',kind='game',title='Win',amount=20,local_date='2026-10-29')
    db.add(old);db.commit()
    configure(db,monkeypatch)
    assert balance(db,st.id)==balance(db,other.id)==0
    assert service.balance_and_earned(db,acc)==(0,0)
    assert db.query(models.CoinTransaction).count()==2 and db.query(MinarLedger).one().amount==20
    snapshot=json.loads(db.get(models.CoinLaunch,1).balance_snapshot)
    assert snapshot=={str(st.id):120,str(other.id):77}
    assert build_coins(db,st).total==0 and not build_coins(db,st).recent
    totals=client.get('/coins/totals',headers=H(admin_token)).json()
    assert all(row['total']==0 for row in totals)
    assert client.get('/space/leaderboard').json()[0]['coins']==0
    give_coins(db,st,9,admin_user.id,when=datetime(2026,10,29,12,1))
    coin_launch.reset_all(db,keep_test_coins=True);db.commit()
    assert balance(db,st.id)==9  # Retry must not erase subsequently earned coins.
    with pytest.raises(ValueError):coin_launch.reset_all(db,keep_test_coins=False)


def test_games_reward_lightning_without_test_coins(client,db,acct,monkeypatch):
    now=datetime.utcnow()
    assert coin_launch.LAUNCH_AT==datetime(2026,11,1,19)
    monkeypatch.setattr(coin_launch,'LAUNCH_AT',now+timedelta(days=7))
    monkeypatch.setattr(coin_launch,'utcnow',lambda:now)
    coin_launch.reset_all(db,keep_test_coins=True);db.commit()
    _,response=play_typing(client,db,10)
    result=response.json()
    assert result['award']==0 and result['state']['lightning']==2 and result['state']['dailyRewardLimit']==3
    assert result['state']['coinPhase']['testMode']
    assert db.query(MinarLedger).filter_by(kind='game').count()==0
    assert C.PRODUCTS['keyboard'][3]==1200 and C.PRODUCTS['stickers'][3]==80
    status=client.get('/space/coins/status')
    assert status.status_code==200 and status.headers['cache-control']=='no-store'
    assert status.json()['startsAt']==coin_launch.LAUNCH_AT.isoformat()+'Z'


@pytest.mark.parametrize('keep',[False,True])
def test_exact_monday_boundary_and_retention_choice(client,db,acct,admin_user,monkeypatch,keep):
    st,_=acct;configure(db,monkeypatch,keep)
    give_coins(db,st,35,admin_user.id,when=coin_launch.LAUNCH_AT-timedelta(seconds=1))
    monkeypatch.setattr(coin_launch,'utcnow',lambda:coin_launch.LAUNCH_AT-timedelta(microseconds=1))
    assert balance(db,st.id)==35 and coin_launch.phase(db)['testMode']
    monkeypatch.setattr(coin_launch,'utcnow',lambda:coin_launch.LAUNCH_AT)
    assert not coin_launch.phase(db)['testMode']
    assert balance(db,st.id)==(35 if keep else 0)
    give_coins(db,st,10,admin_user.id,when=coin_launch.LAUNCH_AT)
    assert balance(db,st.id)==(45 if keep else 10)
    assert service.balance_and_earned(db,db.query(MinarAccount).one())[0]==balance(db,st.id)
    assert build_coins(db,st).total==balance(db,st.id)
    before=balance(db,st.id)
    coin_launch.reset_all(db,keep_test_coins=keep);db.commit()
    assert balance(db,st.id)==before


def test_test_coins_cannot_buy_real_or_digital_gifts(client,db,acct,admin_user,monkeypatch):
    st,_=acct;configure(db,monkeypatch);give_coins(db,st,3000,admin_user.id,when=datetime(2026,10,29,12,1))
    db.add(MinarStock(product_id='stickers',quantity=1));db.commit()
    for product in ['cap','stickers']:
        response=post(client,'/shop/purchases',{'productId':product,'requestId':'test-mode-purchase-'+product})
        assert response.status_code==409 and 'Test coinlari' in response.json()['message']
    assert balance(db,st.id)==3000 and db.query(MinarPurchase).count()==0
    monkeypatch.setattr(coin_launch,'utcnow',lambda:coin_launch.LAUNCH_AT)
    assert post(client,'/shop/purchases',{'productId':'stickers','requestId':'monday-real-purchase'}).status_code==200


def test_old_debits_and_old_gift_refunds_cannot_restore_erased_coins(client,db,acct,admin_user,admin_token,monkeypatch):
    st,_=acct;give_coins(db,st,100,admin_user.id)
    db.add(MinarStock(product_id='stickers',quantity=1));db.commit()
    assert post(client,'/shop/purchases',{'productId':'stickers','requestId':'previous-gift-intent'}).status_code==200
    order=db.query(MinarPurchase).one()
    debit=models.CoinTransaction(student_id=st.id,teacher_id=admin_user.id,amount=-10,reason='Old deduction')
    db.add(debit);db.commit();configure(db,monkeypatch)
    assert client.delete(f'/coins/transactions/{debit.id}',headers=H(admin_token)).status_code==409
    assert client.patch(f'/space/admin/orders/{order.id}',json={'status':'cancelled'},headers=H(admin_token)).status_code==200
    assert balance(db,st.id)==0 and db.query(MinarStock).one().quantity==1
    assert db.query(MinarLedger).filter_by(kind='refund').one().amount==0


def test_reset_cannot_be_started_late(client,db,acct,monkeypatch):
    monkeypatch.setattr(coin_launch,'utcnow',lambda:coin_launch.LAUNCH_AT)
    with pytest.raises(ValueError,match='passed'):coin_launch.reset_all(db,keep_test_coins=True)
    assert db.query(models.CoinLaunch).count()==0
