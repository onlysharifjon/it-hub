import pytest
from datetime import timedelta
from fastapi import HTTPException
from backend import models,tz
from backend.main import _award_coins,_teacher_coin_budget,save_attendance,delete_attendance_date
from backend.reward_policy import student_used,budgets
from backend.minar import service,catalog as C
from backend.minar.models import MinarAccount,MinarLedger
from backend.tests.conftest import _create_user
from backend.tests.test_minar import _minar_env,acct,play_typing,post

@pytest.fixture
def classroom(db):
 t=_create_user(db,'coin-teacher','pass123',models.UserRole.teacher)
 s=models.Student(full_name='Lola Test',phone1='+998901234567',is_active=True,is_archived=False)
 g=models.Group(name='Coin G1',teacher_id=t.id,is_active=True)
 db.add_all([s,g]);db.flush();db.add(models.GroupStudent(student_id=s.id,group_id=g.id));db.commit()
 return t,s,g

@pytest.mark.parametrize('xp,level',[(0,1),(1999,1),(2000,2),(3999,2),(4000,3),(8000,4),(16000,5),(128000,8)])
def test_levels(xp,level):assert C.level_of(xp)==level

def test_shared_cap(db,classroom):
 t,s,g=classroom
 _award_coins(db,t,student_id=s.id,group_id=g.id,amount=69,reason='Vazifa');db.commit()
 t2=_create_user(db,'teacher2','pass123',models.UserRole.teacher)
 g2=models.Group(name='G2',teacher_id=t2.id,is_active=True);db.add(g2);db.flush();db.add(models.GroupStudent(student_id=s.id,group_id=g2.id));db.commit()
 _award_coins(db,t2,student_id=s.id,group_id=g2.id,amount=1,reason='Test');db.commit()
 with pytest.raises(HTTPException):_award_coins(db,t2,student_id=s.id,group_id=g2.id,amount=1,reason='Vazifa')
 db.rollback();assert student_used(db,s.id)==70
 assert _teacher_coin_budget(db,t.id)==70
 assert budgets(db,t)[0]['students'][0]['remaining']==0

def test_admin_cap(db,classroom):
 t,s,g=classroom;a=_create_user(db,'coin-admin','pass123',models.UserRole.admin)
 with pytest.raises(HTTPException):_award_coins(db,a,student_id=s.id,group_id=g.id,amount=71,reason='Test')

def test_foreign_group(db,classroom):
 t,s,g=classroom;other=_create_user(db,'other','pass123',models.UserRole.teacher)
 with pytest.raises(HTTPException):_award_coins(db,other,student_id=s.id,group_id=g.id,amount=1,reason='Test')

def test_attendance_idempotent_reversible(db,classroom):
 t,s,g=classroom;day=tz.today().isoformat();p=[{'student_id':s.id,'is_present':True}]
 for _ in range(3):save_attendance(g.id,day,p,db,t)
 assert db.query(models.CoinTransaction).count()==1
 save_attendance(g.id,day,[{'student_id':s.id,'is_present':False}],db,t)
 assert sum(x.amount for x in db.query(models.CoinTransaction).all())==0
 save_attendance(g.id,day,p,db,t)
 assert sum(x.amount for x in db.query(models.CoinTransaction).all())==1
 delete_attendance_date(g.id,day,db,t)
 assert sum(x.amount for x in db.query(models.CoinTransaction).all())==0

def test_attendance_at_cap(db,classroom):
 t,s,g=classroom;_award_coins(db,t,student_id=s.id,group_id=g.id,amount=70,reason='Vazifa');db.commit()
 save_attendance(g.id,tz.today().isoformat(),[{'student_id':s.id,'is_present':True}],db,t)
 assert student_used(db,s.id)==70 and db.query(models.Attendance).one().is_present

def test_month_boundary(db,classroom):
 t,s,g=classroom;start,_=tz.month_bounds(tz.now().year,tz.now().month)
 db.add(models.CoinTransaction(student_id=s.id,teacher_id=t.id,group_id=g.id,amount=70,created_at=start-timedelta(seconds=1)));db.commit()
 assert student_used(db,s.id)==0
 _award_coins(db,t,student_id=s.id,group_id=g.id,amount=70,reason='Test');db.commit();assert student_used(db,s.id)==70

def test_checkin_one_time(client,db,acct):
 before=db.query(MinarAccount).one().xp
 a=post(client,'/rewards/check-in').json();b=post(client,'/rewards/check-in').json()
 assert a['award']==b['award']==0
 assert a['state']['xp']==b['state']['xp']==before+20
 assert a['state']['balance']==0

def test_verified_game_limits(client,db,acct):
 initial=db.query(MinarAccount).one().xp
 for i in range(4):
  _,r=play_typing(client,db,10);assert r.status_code==200,r.text
  s=r.json()['state'];assert r.json()['award']==0 and s['balance']==0
  assert s['lightning']==min(i+1,3)*2
  assert s['xp']==initial+min(i+1,3)*5
 assert s['gameRewards']['typing']==3
 assert db.query(MinarLedger).filter(MinarLedger.amount>0).count()==0

def test_hero_lock(client,db,acct):
 assert post(client,'/avatar/character',{'character':'hero50'}).status_code==403
 a=db.query(MinarAccount).one();a.xp=2000;db.commit()
 r=post(client,'/avatar/character',{'character':'hero05'});assert r.status_code==200,r.text

def test_profile_whitelist(client,db,acct):
 a=db.query(MinarAccount).one();p=service.public_profile(db,a,a.login_id)
 assert set(p)=={'id','name','course','character','level','xp','lightning','coins','badges','equipment'}
 with pytest.raises(Exception):service.public_profile(db,a,'missing')

def test_active_profiles_visible_and_coin_does_not_rank(client,db,acct):
 from backend.minar.errors import MinarError
 me=db.query(MinarAccount).one();others=[]
 for i in range(4):
  st=models.Student(full_name=f'Top {i}',phone1=f'+99890000000{i}',is_active=True,is_archived=False);db.add(st);db.flush()
  a=MinarAccount(student_id=st.id,login_id=f'TOP{i}',password_hash='unused',course='HTML',xp=(i+1)*2000,is_active=True,is_test=False)
  db.add(a);db.flush();others.append(a)
 db.commit()
 rows=service.leaderboard(db,me,'lightning','all','all')
 assert rows[0]['id']==others[3].login_id
 assert service.public_profile(db,me,others[3].login_id)['xp']==8000
 assert service.public_profile(db,me,others[0].login_id)['xp']==2000

def test_student_actions_cannot_credit_coin(client,db,acct):
 r=post(client,'/courses/complete',{'index':0});assert r.status_code==410
 from backend.tests.test_group_learning import add_content
 from backend.minar import study
 c=add_content(db);a=db.query(MinarAccount).one()
 r=post(client,f'/study/content/{c.id}/assess',{'requestId':'reward-policy-001','answers':[q['answer'] for q in study.questions_for(c,a.id)]})
 assert r.status_code==200 and r.json()['award']==0
 r=post(client,'/quests/claim',{'quest':'lesson'});assert r.status_code==200 and r.json()['award']==0 and r.json()['state']['balance']==0
 # Explicit lower-level guard also protects future reward callers.
 a=db.query(MinarAccount).one()
 with pytest.raises(Exception):service._credit(db,a,1,'bypass','game','bypass')

def test_attendance_rejects_duplicate_and_invalid_boolean(db,classroom):
 t,s,g=classroom;p={'student_id':s.id,'is_present':True}
 with pytest.raises(HTTPException):save_attendance(g.id,tz.today().isoformat(),[p,p],db,t)
 with pytest.raises(HTTPException):save_attendance(g.id,tz.today().isoformat(),[{'student_id':s.id,'is_present':1}],db,t)

def test_xp_storage_migration_keeps_balances_and_accounts(db,classroom):
 import importlib.util
 from pathlib import Path
 from alembic.migration import MigrationContext
 from alembic.operations import Operations
 t,s,g=classroom
 account=MinarAccount(student_id=s.id,login_id='BIGXP',password_hash='unused',xp=2147483648)
 db.add(account);db.commit()
 path=Path(__file__).parents[1]/'alembic/versions/20261101a_reward_xp_bigint.py'
 spec=importlib.util.spec_from_file_location('xp_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 with Operations.context(MigrationContext.configure(db.connection())):module.upgrade()
 db.commit();db.expire_all();assert db.query(MinarAccount).one().xp==2147483648
 with Operations.context(MigrationContext.configure(db.connection())):
  with pytest.raises(RuntimeError):module.downgrade()


def test_student_bootstrap_keeps_wallet_without_staff_budget(client, db, acct):
 account = db.query(MinarAccount).one()
 state = service.build_state(db, account)
 assert "balance" in state
 assert "coinAllowance" not in state
 from backend.minar.assistant import _offline
 assert "70" not in _offline("Coin qanday olinadi?")
