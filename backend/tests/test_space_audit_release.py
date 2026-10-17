"""Regression coverage for audit fixes and full student/staff workflows."""
import json
import uuid
from datetime import datetime,timedelta
import pytest
from backend import models,tz
from backend.minar import service,study,assistant
from backend.minar.models import (MinarAccount,MinarBattle,MinarLedger,MinarResult,MinarStock,MinarNotification,
    MinarContent,MinarProgress,MinarLearningAttempt,MinarRevision,MinarLoginToken,MinarGroupCourse)
from backend.tests.test_minar import acct,_minar_env,H,post,new_account,login,give_coins,start_game


def account(db):return db.query(MinarAccount).one()

def content(client,token,**extra):
    payload={'course':'HTML','topic':'Teglar','title':'Talaba materiali','body':'Sarlavha uchun h1 ishlating.',
        'exercise':'Bir sarlavha yozing.','questions':[{'q':'Sarlavha tegi?','options':['h1','img','br'],'answer':0,'explain':'h1 asosiy sarlavhadir.'}],
        'published':True,'position':1,**extra}
    r=client.post('/space/admin/study/content',json=payload,headers=H(token));assert r.status_code==200,r.text
    return r.json()


def test_wallet_shared_and_reversal_preserves_history(client,db,acct,admin_token,admin_user):
    from backend.parent.service import build_coins
    st,_=acct;give_coins(db,st,100,admin_user.id)
    original=db.query(models.CoinTransaction).one()
    assert post(client,'/shop/purchases',{'productId':'cap','requestId':'purchase-intent-01'}).status_code==200
    assert build_coins(db,st).total==35
    r=client.post('/coins/deduct',json={'student_id':st.id,'amount':40,'reason':'test'},headers=H(admin_token));assert r.status_code==400
    # Already spent grant cannot be reversed into a negative wallet.
    assert client.delete(f'/coins/transactions/{original.id}',headers=H(admin_token)).status_code==400
    give_coins(db,st,100,admin_user.id)
    assert client.delete(f'/coins/transactions/{original.id}',headers=H(admin_token)).status_code==204
    db.expire_all();assert db.query(models.CoinTransaction).filter_by(id=original.id).first()
    assert db.query(models.CoinTransaction).filter_by(reversal_of_id=original.id).count()==1
    assert client.delete(f'/coins/transactions/{original.id}',headers=H(admin_token)).status_code==409
    assert build_coins(db,st).total==35
    assert service.balance_and_earned(db,account(db))==(35,100)


def test_battle_fake_losses_and_duplicate_match_cannot_mint(client,db,acct):
    a=account(db)
    fake={'game':'battle','mode':'typing','id':'fake-result-01','matchId':'fake-match-01','won':False,'score':0}
    assert post(client,'/games/results',{'result':fake}).status_code==400
    assert db.query(MinarResult).count()==0
    b=MinarBattle(code='AUDIT1',room_id=str(uuid.uuid4()),mode='typing',course='HTML',host_account_id=a.id,status='finished',match_id=str(uuid.uuid4()),winner_account_id=a.id,host_score=100)
    db.add(b);db.commit()
    first=post(client,'/games/results',{'result':{**fake,'matchId':b.match_id,'won':False}}).json()
    second=post(client,'/games/results',{'result':{**fake,'id':'different-client-id','matchId':b.match_id,'won':True}}).json()
    assert first['award']==15 and second['state']['xp']==first['state']['xp']
    assert second['state']['balance']==first['state']['balance'] and db.query(MinarResult).count()==1


def test_ztype_fake_indices_rejected(client,db,acct):
    s=start_game(client,'ztype')
    r=post(client,'/games/results',{'result':{'game':'ztype','session':s['id'],'hits':[0,1,2,3,4],'duration':2}})
    assert r.status_code==400 and db.query(MinarResult).count()==0
    assert post(client,'/games/hit',{'session':s['id'],'index':40,'word':s['words'][40]}).status_code==400


def test_server_js_does_not_trust_output_and_limits_execution(client,acct):
    r=post(client,'/playground/js-1/check',{'js':'console.log("WRONG")','output':['Salom, Minar!']}).json()
    assert not r['solved'] and not r['award']
    assert post(client,'/playground/run',{'js':'`${(()=>{while(true){}})()}`'}).json()['error']
    r=post(client,'/playground/run',{'js':'console.log(typeof process, typeof require, typeof fetch)'}).json()
    assert r['output']==['undefined undefined undefined']
    r=post(client,'/playground/run',{'js':'JSON.stringify=()=>\'["forged"]\';Array.prototype.toJSON=()=>["forged"];'}).json()
    assert r['output']==[]
    r=post(client,'/playground/js-5/check',{'js':'function add(a,b){return 5};console.log(add(2,3))','output':['5']}).json()
    assert not r['solved']


def test_qr_revoked_on_disable_and_password_reset(client,db,acct,metodist_token):
    from backend.minar.auth import issue_login_token
    a=account(db);raw=issue_login_token(db,a,None);db.commit()
    assert client.post(f'/space/admin/accounts/{a.student_id}/reset-password',headers=H(metodist_token)).status_code==200
    assert db.query(MinarLoginToken).filter_by(account_id=a.id).count()==0
    assert post(client,'/auth/qr',{'token':raw}).status_code in (400,401)


def test_old_pending_and_same_day_different_groups(client,db,acct):
    st,_=acct;g=db.query(models.Group).one();today=tz.today()
    for i in range(45):db.add(models.Homework(group_id=g.id,text='Vazifa '+str(i),lesson_date=today-timedelta(days=i)))
    g2=models.Group(name='Ikkinchi',stage='foundation',is_active=True);db.add(g2);db.flush()
    db.add_all([models.Attendance(group_id=g.id,student_id=st.id,lesson_date=today,is_present=True),models.Attendance(group_id=g2.id,student_id=st.id,lesson_date=today,is_present=False)])
    db.commit();s=client.get('/space/students/me/bootstrap').json()
    assert s['homeworkPending']==45
    assert len(client.get('/space/homework?status=pending&offset=30').json())==15
    assert {x['status'] for x in s['attendance']}=={'present','absent'}


def test_visible_notifications_only_and_real_rank(client,db,acct):
    a=account(db)
    db.add_all([MinarNotification(account_id=a.id,kind='system',title=str(i)) for i in range(60)])
    db.commit();page=client.get('/space/notifications').json()
    assert post(client,'/notifications/read',{}).status_code==400
    assert post(client,'/notifications/read',{'ids':[n['id'] for n in page['items']]}).json()['unread']==10
    assert len(client.get('/space/notifications?before='+str(page['next'])).json()['items'])==10
    a.is_test=True;db.commit()
    assert client.get('/space/leaderboard').json()==[]


def test_assistant_redacts_entire_history(client,acct,monkeypatch):
    seen=[]
    monkeypatch.setattr(assistant,'_ask_model',lambda messages,course:seen.extend(messages) or 'Javob')
    r=post(client,'/assistant/messages',{'messages':[{'role':'user','content':'Parolim: private-secret'}, {'role':'assistant','content':'Yozmang'}, {'role':'user','content':'Flexbox nima?'}]})
    assert r.status_code==200 and all('private-secret' not in m['content'] for m in seen)


def test_order_stock_idempotency_refund_and_no_refund_in_earned(client,db,acct,admin_user,admin_token):
    st,_=acct;give_coins(db,st,100,admin_user.id)
    assert client.put('/space/admin/stock/stickers',json={'quantity':1},headers=H(admin_token)).status_code==200
    payload={'productId':'stickers','requestId':'intent-stock-001'}
    one=post(client,'/shop/purchases',payload);assert one.status_code==200,one.text
    assert post(client,'/shop/purchases',payload).status_code==200
    orders=client.get('/space/admin/orders',headers=H(admin_token)).json();assert len(orders)==1
    oid=orders[0]['id'];url='/space/admin/orders/'+oid
    assert client.patch(url,json={'status':'collected'},headers=H(admin_token)).status_code==409
    assert client.patch(url,json={'status':'cancelled'},headers=H(admin_token)).status_code==200
    assert client.patch(url,json={'status':'cancelled'},headers=H(admin_token)).status_code==200
    assert client.patch(url,json={'status':'ready'},headers=H(admin_token)).status_code==409
    db.expire_all();assert service.balance_and_earned(db,account(db))==(100,100)
    assert db.query(MinarStock).one().quantity==1


def test_student_content_assess_review_and_permissions(client,db,acct,admin_token,teacher_token):
    c=content(client,admin_token)
    assert client.post('/space/admin/study/content',json=c,headers=H(teacher_token)).status_code==403
    public=client.get('/space/study/content/'+str(c['id'])).json()
    assert all('answer' not in q and 'explain' not in q for q in public['questions'])
    answer=public['questions'][0]['options'].index('h1');key='assessment-intent-1'
    url=f"/study/content/{c['id']}/assess"
    result=post(client,url,{'answers':[answer],'requestId':key}).json();assert result['passed'] and result['award']==5
    assert post(client,url,{'answers':[answer],'requestId':key}).json()['award']==0
    a=account(db);p=db.query(MinarProgress).one();p.next_review_at=datetime.utcnow()-timedelta(days=1);db.commit()
    assert post(client,url,{'answers':[answer],'requestId':'review-intent-001'}).json()['award']==2
    knowledge=client.get('/space/study/knowledge').json();assert knowledge['topics'][0]['mastery']==100
    assert db.query(MinarLearningAttempt).count()==2
    c['published']=False
    assert client.post('/space/admin/study/content',json=c,headers=H(admin_token)).status_code==200
    assert client.get('/space/study/content/'+str(c['id'])).status_code==404


def test_homework_full_revision_and_private_files(client,db,acct,admin_token,teacher_token):
    st,_=acct;a=account(db);g=db.query(models.Group).one()
    hw=models.Homework(group_id=g.id,text='Mustaqil ish',lesson_date=tz.today());db.add(hw);db.commit()
    upload=client.post('/space/attachments',files={'file':('ish.pdf',b'%PDF-1.4 test','application/pdf')});assert upload.status_code==200
    aid=upload.json()['id'];payload={'answer':'Birinchi javob','link':None,'attachments':[aid]}
    assert client.put(f'/space/homework/{hw.id}/draft',json=payload).status_code==200
    assert client.get(f'/space/homework/{hw.id}/draft').json()['draft']['answer']=='Birinchi javob'
    assert post(client,f'/homework/{hw.id}/submit',payload).status_code==200
    url=f'/space/admin/study/reviews/{hw.id}/{a.id}'
    review={'status':'returned','comment':'Misol qo‘shing','rubric':{'correctness':2,'clarity':1,'independence':3}}
    assert client.post(url,json=review,headers=H(teacher_token)).status_code in (403,404)
    assert client.post(url,json=review,headers=H(admin_token)).status_code==200
    assert client.get('/space/homework?status=pending').json()[0]['status']=='returned'
    assert post(client,f'/homework/{hw.id}/submit',{**payload,'answer':'Tuzatilgan javob'}).status_code==200
    assert client.post(url,json={**review,'status':'graded','coins':3},headers=H(admin_token)).status_code==200
    assert db.query(MinarRevision).count()==4
    assert client.get('/space/attachments/'+aid).status_code==200
    assert client.get('/space/admin/study/attachments/'+aid,headers=H(teacher_token)).status_code==404
    assert client.get('/space/admin/study/attachments/'+aid,headers=H(admin_token)).status_code==200


def test_portfolio_requires_review_and_optin_and_can_revoke(client,db,acct,admin_token):
    p=post(client,'/portfolio',{'title':'Saytim','description':'HTML loyiham','url':'https://example.com'}).json()
    assert post(client,f"/portfolio/{p['id']}/share",{'enabled':True}).status_code==409
    assert client.post(f"/space/admin/study/portfolio/{p['id']}",json={'status':'approved'},headers=H(admin_token)).status_code==200
    p=post(client,f"/portfolio/{p['id']}/share",{'enabled':True}).json();token=p['shareToken']
    page=client.get('/space/public/portfolio/'+token);assert page.status_code==200 and 'Azizbek' not in page.text
    assert post(client,f"/portfolio/{p['id']}/share",{'enabled':False}).status_code==200
    assert client.get('/space/public/portfolio/'+token).status_code==404


def test_mentor_thread_assignment_and_replies(client,db,acct,admin_token,teacher_user,teacher_token):
    a=account(db);g=db.query(models.Group).one();g.teacher_id=teacher_user.id;db.commit()
    client.get('/space/students/me/bootstrap')
    t=post(client,'/help',{'subject':'Savolim','body':'h1 qanday ishlaydi?','groupId':g.id}).json();assert t['status']=='open'
    r=client.post(f"/space/admin/study/help/{t['id']}",json={'body':'Sarlavha uchun ishlating.','status':'answered'},headers=H(teacher_token));assert r.status_code==200,r.text
    assert client.get('/space/help').json()[0]['messages'][-1]['staff'] is True
    assert client.get('/space/admin/guides',headers=H(teacher_token)).status_code==403
    assert client.get('/space/admin/guides',headers=H(admin_token)).status_code==200


def test_history_aggregates_beyond_bootstrap_cap(client,db,acct,admin_user):
    st,_=acct
    db.add_all([models.CoinTransaction(student_id=st.id,teacher_id=admin_user.id,amount=1,reason='x') for i in range(550)])
    db.commit();data=client.get('/space/history').json()
    assert data['total']==550 and data['earned']==550 and len(data['items'])==50
    assert client.get('/space/history?offset=500').json()['next'] is None
    assert len(client.get('/space/students/me/bootstrap').json()['history'])==30

@pytest.fixture
def admin_user(db):
    from backend.main import hash_password
    user=models.User(username='audit_admin',hashed_password=hash_password('AuditPass123'),role='admin',is_active=True)
    db.add(user);db.commit();return user

@pytest.fixture
def admin_token(client,admin_user):
    r=client.post('/auth/login',json={'username':'audit_admin','password':'AuditPass123'})
    assert r.status_code==200
    return r.json()['access_token']


def test_postgres_concurrent_crm_and_space_spend_never_overdraw(client,db,acct,admin_user,admin_token):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi.testclient import TestClient
    from backend.main import app
    if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL row locks required')
    st,creds=acct;give_coins(db,st,100,admin_user.id)
    student_client=TestClient(app);login(student_client,creds)
    def buy():return student_client.post('/space/shop/purchases',json={'productId':'cap','requestId':'concurrent-purchase-1'}).status_code
    def deduct():return TestClient(app).post('/coins/deduct',json={'student_id':st.id,'amount':60,'reason':'Concurrency test'},headers=H(admin_token)).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(lambda fn:fn(),[buy,deduct]))
    assert sorted(codes) in ([200,400],[201,400]),codes
    db.expire_all();assert service.balance_and_earned(db,account(db))[0] in (35,40)


def test_postgres_two_students_cannot_buy_last_stock_twice(client,db,acct,admin_user,metodist_token):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi.testclient import TestClient
    from backend.main import app
    if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL row locks required')
    st,creds=acct;st2,creds2=new_account(client,db,metodist_token,name='Second Test')
    give_coins(db,st,100,admin_user.id);give_coins(db,st2,100,admin_user.id)
    db.add(MinarStock(product_id='stickers',quantity=1));db.commit()
    clients=[TestClient(app),TestClient(app)]
    for c,cred in zip(clients,[creds,creds2]):login(c,cred)
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes=list(pool.map(lambda c:c.post('/space/shop/purchases',json={'productId':'stickers','requestId':'last-stock-intent'}).status_code,clients))
    assert sorted(codes)==[200,409],codes
    db.expire_all();assert db.query(MinarStock).one().quantity==0


def test_guides_are_downloadable_only_by_superadmin(client,admin_token,teacher_token,metodist_token):
    for token in (teacher_token,metodist_token):
        assert client.get('/space/admin/guides/space-guide.pdf',headers=H(token)).status_code==403
    r=client.get('/space/admin/guides/space-guide.pdf',headers=H(admin_token))
    assert r.status_code==200 and r.content.startswith(b'%PDF') and 'attachment' in r.headers['content-disposition']
    assert client.get('/space/admin/guides/../models.py',headers=H(admin_token)).status_code==404


def test_completed_course_has_daily_practice_between_review_dates(client,db,acct,admin_token):
    c=content(client,admin_token)
    public=client.get('/space/study/content/'+str(c['id'])).json()
    answer=public['questions'][0]['options'].index('h1')
    url=f"/study/content/{c['id']}/assess"
    assert post(client,url,{'answers':[answer],'requestId':'first-complete-01'}).json()['award']==5
    p=db.query(MinarProgress).one();due=p.next_review_at
    assert client.get('/space/study/today').json()['continue']['dailyPractice']
    assert post(client,url,{'answers':[answer],'requestId':'daily-practice-01'}).json()['award']==2
    assert post(client,url,{'answers':[answer],'requestId':'daily-practice-02'}).json()['award']==0
    db.refresh(p);assert p.next_review_at==due
    assert account(db).xp==30


def test_old_month_reversal_does_not_inflate_current_teacher_budget(client,db,acct,admin_token,admin_user):
    from backend.main import _coins_spent_this_month
    st,_=acct;old=models.CoinTransaction(student_id=st.id,teacher_id=admin_user.id,amount=80,created_at=datetime.utcnow()-timedelta(days=40))
    now=models.CoinTransaction(student_id=st.id,teacher_id=admin_user.id,amount=15)
    db.add_all([old,now]);db.commit()
    assert client.delete(f'/coins/transactions/{old.id}',headers=H(admin_token)).status_code==204
    assert _coins_spent_this_month(db,admin_user.id)==15


def test_today_earned_uses_complete_history(client,db,acct,admin_user):
    st,_=acct
    db.add_all([models.CoinTransaction(student_id=st.id,teacher_id=admin_user.id,amount=1) for _ in range(65)])
    db.commit();state=service.build_state(db,account(db))
    assert len(state['history'])==30 and state['earnedToday']==65


def test_readiness_fails_when_database_or_redis_is_unavailable(monkeypatch):
    from backend import readiness
    class Db:
        failed=False
        def execute(self,_):
            if self.failed:raise RuntimeError('unavailable')
        def close(self):pass
    db=Db();monkeypatch.setattr(readiness,'SessionLocal',lambda:db)
    monkeypatch.setattr(readiness.security,'REDIS_URL','redis://test')
    class Redis:
        def ping(self):return True
    monkeypatch.setattr(readiness.security,'_get_redis',lambda:Redis())
    assert readiness.check().status_code==200
    db.failed=True;assert readiness.check().status_code==503
    db.failed=False;monkeypatch.setattr(readiness.security,'_get_redis',lambda:None)
    assert readiness.check().status_code==503
