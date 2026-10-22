"""Assessment workflow, authorization, server deadlines and wallet integrity."""
import json
from datetime import datetime,timedelta,timezone
from fastapi.testclient import TestClient
from backend.main import app
from backend import models
from backend.minar.academy_models import AcademyTopic,AcademyAssignment,AcademyAttempt,AcademyPractice,AcademyBonus,AcademyNotice
from backend.minar.models import MinarAccount,MinarLedger
import pytest
from backend.tests.conftest import _create_user, _login
from backend.tests.test_minar import acct,_minar_env,H,post,new_account,login


def provision(client,db,token,**extra):
    lib=client.get('/space/admin/academy/library',headers=H(token));assert lib.status_code==200,lib.text
    item=lib.json()[0]
    r=client.post('/space/admin/academy/import',headers=H(token),json={'slugs':[item['slug']]});assert r.status_code==200,r.text
    topic=db.query(AcademyTopic).filter_by(slug=item['slug']).one()
    r=client.post(f'/space/admin/academy/topics/{topic.id}',headers=H(token),json={'published':True});assert r.status_code==200,r.text
    body={'topicId':topic.id,'groupId':db.query(models.Group).first().id,'count':4,'minutes':10,'maxAttempts':2,'dueAt':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),**extra}
    r=client.post('/space/admin/academy/assignments',headers=H(token),json=body);assert r.status_code==200,r.text
    return topic,r.json()


def start(client,a):
    r=post(client,f'/academy/assignments/{a["id"]}/start',{'language':'ru'});assert r.status_code==200,r.text
    return r.json()


def correct_answers(db,key):
    db.expire_all();a=db.get(AcademyAttempt,key)
    return {q['id']:q['answer'] for q in json.loads(a.snapshot)}


def test_import_publish_attempt_snapshot_and_rewards(client,db,acct,admin_token):
    topic,a=provision(client,db,admin_token)
    assert client.post('/space/admin/academy/import',headers=H(admin_token),json={'slugs':[topic.slug]}).json()['added']==0
    before=client.get('/space/academy').json();assert len(before['topics'])==1
    row=start(client,a);assert all('answer' not in q for q in row['questions']);assert row['language']=='ru'
    assert start(client,a)['id']==row['id']
    answers=correct_answers(db,row['id'])
    assert post(client,'/academy/attempts/'+row['id'],{'answers':{'foreign':1}}).status_code==400
    assert post(client,'/academy/attempts/'+row['id'],{'answers':answers}).json()['score'] is None
    # Editing the bank does not change an in-flight exam.
    topic=db.get(AcademyTopic,topic.id);d=json.loads(topic.data);d['questions'][0]['q']='Edited';topic.data=json.dumps(d);db.commit()
    result=post(client,'/academy/attempts/'+row['id'],{'submit':True}).json();assert result['score']==100
    assert not any('answer' in x for x in result['review'])
    assert post(client,'/academy/attempts/'+row['id'],{'submit':True,'answers':{}}).json()['score']==100
    second=start(client,a);result2=post(client,'/academy/attempts/'+second['id'],{'answers':correct_answers(db,second['id']),'submit':True});assert result2.json()['score']==100
    assert db.query(MinarLedger).filter(MinarLedger.ref_key.like('academy-pass:%')).count()==1
    assert post(client,f'/academy/assignments/{a["id"]}/start',{}).status_code==409


def test_deadline_rejects_late_answers_and_records_mistakes(client,db,acct,admin_token):
    _,a=provision(client,db,admin_token);row=start(client,a);answers=correct_answers(db,row['id'])
    attempt=db.get(AcademyAttempt,row['id']);attempt.deadline=datetime.utcnow()-timedelta(seconds=1);db.commit()
    r=post(client,'/academy/attempts/'+row['id'],{'answers':answers,'submit':True});assert r.status_code==200,r.text
    assert r.json()['score']==0 and db.query(AcademyPractice).count()==4
    practice=client.get('/space/academy/practice').json();assert practice['remaining']==4
    m=db.query(AcademyPractice).first();correct=json.loads(m.snapshot)['answer']
    for i in range(3):
        db.refresh(m);m.last_answer_at=datetime.utcnow()-timedelta(seconds=11);db.commit()
        r=post(client,f'/academy/practice/{m.id}',{'answer':correct});assert r.status_code==200,r.text
    assert r.json()['resolved'] and r.json()['award']==2
    assert post(client,f'/academy/practice/{m.id}',{'answer':correct}).status_code==409
    assert db.query(MinarLedger).filter_by(ref_key=f'academy-fix:{m.id}').count()==1


def test_ownership_and_teacher_scope(client,db,acct,admin_token,teacher_token,metodist_token):
    _,a=provision(client,db,admin_token);row=start(client,a)
    assert client.get('/space/admin/academy/assignments',headers=H(teacher_token)).json()==[]
    assert client.get('/space/admin/academy/report',headers=H(teacher_token)).json()['attempts']==[]
    assert client.post('/space/admin/academy/assignments',headers=H(teacher_token),json={'topicId':a['topicId'],'groupId':a['groupId'],'dueAt':a['dueAt']}).status_code==403
    _,creds=new_account(client,db,metodist_token,name='Other student');login(client,creds)
    assert client.get('/space/academy/attempts/'+row['id']).status_code==404
    assert post(client,f'/academy/assignments/{a["id"]}/start',{}).status_code==404
    assert client.get('/space/academy/topics/'+str(a['topicId'])).status_code==404
    assert client.post('/space/admin/academy/import',json={'slugs':['mywebsite-st01']}).status_code==401


def test_bonus_daily_limit_and_replay(client,db,acct,admin_token):
    _,assignment=provision(client,db,admin_token)
    assert client.get('/space/academy/bonus').json()['question'] is None
    attempt=start(client,assignment)
    post(client,'/academy/attempts/'+attempt['id'],{'answers':correct_answers(db,attempt['id']),'submit':True})
    for _ in range(10):
        r=client.get('/space/academy/bonus').json();assert r['id']
        assert client.get('/space/academy/bonus').json()['id']==r['id']
        b=db.get(AcademyBonus,r['id']);answer=json.loads(b.snapshot)['answer']
        assert post(client,'/academy/bonus/'+r['id'],{'answer':answer}).json()['award']==1
        assert post(client,'/academy/bonus/'+r['id'],{'answer':answer}).json()['award']==0
    assert client.get('/space/academy/bonus').json()['question'] is None
    assert db.query(MinarLedger).filter(MinarLedger.ref_key.like('academy-bonus:%')).count()==10


def test_scheduled_notices_once_and_report(client,db,acct,admin_token):
    _,a=provision(client,db,admin_token,startsAt=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
    assert post(client,f'/academy/assignments/{a["id"]}/start',{}).status_code==409
    client.get('/space/academy');assert db.query(AcademyNotice).count()==0
    assignment=db.get(AcademyAssignment,a['id']);assignment.starts_at=datetime.utcnow()-timedelta(hours=4);db.commit()
    client.get('/space/academy');client.get('/space/academy');assert db.query(AcademyNotice).count()==2
    row=start(client,a);post(client,'/academy/attempts/'+row['id'],{'submit':True})
    report=client.get('/space/admin/academy/report',headers=H(admin_token)).json()
    assert report['daily']['completed']==1 and report['atRisk'] and len(report['questions'])==4


def test_public_attempt_cookie_scope_close_and_lead(client,db,acct,admin_token):
    _,a=provision(client,db,admin_token,public=True);path='/space/academy/public/'+a['publicToken']
    public=TestClient(app)
    body={'name':'Test Guest','phone':'+998901234568','consent':True,'language':'uz'}
    r=public.post(path+'/start',json=body);assert r.status_code==200,r.text
    key=r.json()['id'];outsider=TestClient(app)
    assert outsider.post(path+'/attempts/'+key,json={}).status_code==404
    assert outsider.post(path+'/start',json=body).status_code==409
    r=public.post(path+'/attempts/'+key,json={'answers':correct_answers(db,key),'submit':True});assert r.json()['score']==100
    r=client.post('/space/admin/academy/attempts/'+key+'/lead',headers=H(admin_token),json={});assert r.status_code==200,r.text
    lid=r.json()['leadId'];assert client.post('/space/admin/academy/attempts/'+key+'/lead',headers=H(admin_token),json={}).json()['leadId']==lid
    assert db.query(models.Lead).count()==1
    client.post(f'/space/admin/academy/assignments/{a["id"]}/status',headers=H(admin_token),json={'active':False})
    assert public.get(path).status_code==404

@pytest.fixture
def admin_user(db):
    return _create_user(db,'academy-admin','academy-password',models.UserRole.admin)

@pytest.fixture
def admin_token(client,admin_user):
    return _login(client,'academy-admin','academy-password')


def test_migration_roundtrip_preserves_crm(tmp_path):
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine,inspect,text
    from alembic.runtime.migration import MigrationContext
    from alembic.operations import Operations
    from backend.database import Base
    engine=create_engine('sqlite:///'+str(tmp_path/'migration.db'))
    Base.metadata.create_all(engine,tables=[t for t in Base.metadata.sorted_tables if not t.name.startswith('minar_academy_')])
    path=Path(__file__).parents[1]/'alembic/versions/20261022a_academy.py'
    spec=importlib.util.spec_from_file_location('academy_migration',path);migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id,username,hashed_password,role,is_active,created_at) VALUES (1,'preserved','hash','teacher',1,CURRENT_TIMESTAMP)"))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            assert len([x for x in inspect(conn).get_table_names() if x.startswith('minar_academy_')])==6
            migration.downgrade()
        assert conn.execute(text('SELECT username FROM users WHERE id=1')).scalar()=='preserved'
    engine.dispose()


def test_public_origin_and_cache_control(client,db,acct,admin_token):
    _,a=provision(client,db,admin_token,public=True)
    path='/space/academy/public/'+a['publicToken']
    assert client.get(path).headers['cache-control']=='no-store'
    r=client.post(path+'/start',json={'name':'Guest Test','phone':'998901234567','consent':True},headers={'Origin':'https://untrusted.example'})
    assert r.status_code==403


def test_translation_validation_and_preview(client,db,acct,admin_token):
    library=client.get('/space/admin/academy/library',headers=H(admin_token)).json()
    assert len(library)==77 and sum(x['questionCount'] for x in library)==924
    preview=client.get('/space/admin/academy/library/'+library[0]['slug'],headers=H(admin_token)).json()
    assert preview['body_ru'] and all(q['q_ru'] for q in preview['questions'])
    topic,_=provision(client,db,admin_token)
    data=json.loads(topic.data);data['questions'][0]['options_ru']=['Only one']
    assert client.post(f'/space/admin/academy/topics/{topic.id}',headers=H(admin_token),json={'data':data,'published':True}).status_code==400


def test_summary_and_scheduler_deliver_digest_once(client,db,acct,admin_token,monkeypatch):
    from backend.minar import academy
    from backend import database
    from backend.tests.conftest import TestSessionLocal
    _,a=provision(client,db,admin_token)
    summary=client.get('/space/academy/summary').json()
    assert summary['pending']==1 and summary['next']['id']==a['id']
    original=academy.tz.to_local
    monkeypatch.setattr(academy.tz,'to_local',lambda value:original(value).replace(hour=21))
    monkeypatch.setattr(database,'SessionLocal',TestSessionLocal)
    academy.scheduled_tick();academy.scheduled_tick()
    db.expire_all()
    assert db.query(models.Notification).filter_by(notification_type='academy_daily').count()==1
    assert db.query(AcademyNotice).filter_by(kind='assigned').count()==1


def test_archived_group_cannot_start_new_assessments(client,db,acct,admin_token):
    _,a=provision(client,db,admin_token)
    group=db.get(models.Group,a['groupId']);group.is_active=False;db.commit()
    assert post(client,f'/academy/assignments/{a["id"]}/start',{}).status_code==404
    assert client.get('/space/academy').json()['topics']==[]
