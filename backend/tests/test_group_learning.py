"""Group-scoped learning and authoritative quiz content regressions."""
import json
from datetime import timedelta
import pytest
from backend import models, tz
from backend.minar import study, games, battles
from backend.minar.errors import MinarError
from backend.minar.models import MinarAccount, MinarContent, MinarGameSession
from backend.tests.test_minar import acct, _minar_env, post, H


def add_content(db, number=1, stage='foundation', linked=True, published=True):
    lesson=db.query(models.Lesson).filter_by(category=stage,lesson_number=number).first()
    if not lesson:
        lesson=models.Lesson(category=stage,lesson_number=number,title=f'{stage} topic {number}',guide='PRIVATE TEACHER GUIDE')
        db.add(lesson);db.flush()
    row=MinarContent(slug=f'{stage}-{number}-{linked}',lesson_id=lesson.id if linked else None,
        course='Foundation' if stage=='foundation' else 'Frontend',topic=lesson.title,title=lesson.title,
        body='Student material',exercise='Practice',published=published,
        questions=json.dumps([{'q':f'{stage} {number} Question {i}', 'options':['Correct','Wrong','Another'], 'answer':0, 'explain':'Explanation'} for i in range(5)]))
    db.add(row);db.commit();return row


def test_only_selected_group_current_and_taught_materials_are_accessible(client,db,acct):
    a=db.query(MinarAccount).one();group=db.query(models.Group).one()
    current=add_content(db);future=add_content(db,2);other=add_content(db,1,'frontend')
    unlinked=add_content(db,8,linked=False);unlinked.course='HTML';db.commit()
    path=client.get('/space/study/path').json()
    assert [c['id'] for c in path['content']]==[current.id]
    assert path['course']=='Foundation' and path['currentLessonId']==current.lesson_id
    assert [l['status'] for l in path['lessons']]==['current','upcoming','upcoming']
    assert 'PRIVATE' not in str(path) and 'answer' not in str(path['content'])
    for row in [future,other,unlinked]:
        assert client.get(f'/space/study/content/{row.id}').status_code==404
        assert post(client,f'/study/content/{row.id}/assess',{'requestId':'not-allowed-123','answers':[0]*5}).status_code==404
    db.add(models.Attendance(group_id=group.id,student_id=a.student_id,lesson_date=tz.today(),is_present=True));db.commit()
    assert {c['id'] for c in client.get('/space/study/content').json()}=={current.id,future.id}


def test_group_switch_and_left_membership_cannot_leak_content(client,db,acct):
    a=db.query(MinarAccount).one();first=add_content(db);second=add_content(db,1,'frontend')
    g=models.Group(name='Frontend QA',stage='frontend',is_active=True);db.add(g);db.flush()
    member=models.GroupStudent(group_id=g.id,student_id=a.student_id);db.add(member);db.commit()
    assert post(client,'/study/enrollment',{'groupId':g.id}).status_code==200
    assert [c['id'] for c in client.get('/space/study/content').json()]==[second.id]
    assert client.get(f'/space/study/content/{first.id}').status_code==404
    member.left_at=tz.today();db.commit()
    assert client.get(f'/space/study/content/{second.id}').status_code==404
    assert post(client,'/study/enrollment',{'groupId':g.id}).status_code==404


def test_no_group_and_missing_program_do_not_fall_back_to_html(client,db,acct):
    add_content(db);a=db.query(MinarAccount).one()
    db.query(models.GroupStudent).update({'left_at':tz.today()});db.commit()
    path=client.get('/space/study/path').json()
    assert path['group'] is None and path['content']==[]
    assert post(client,'/games/start',{'game':'quiz'}).status_code==409
    assert post(client,'/battles',{'mode':'quiz'}).status_code==409
    assert post(client,'/games/start',{'game':'bug'}).status_code==400


def test_quiz_snapshot_survives_teacher_edits_and_scores_on_server(client,db,acct):
    content=add_content(db)
    response=post(client,'/games/start',{'game':'quiz','course':'JavaScript'});assert response.status_code==200,response.text
    public=response.json();assert all('answer' not in q and 'explain' not in q for q in public['questions'])
    row=db.get(MinarGameSession,public['id']);snapshot=games.session_questions(row)
    content.questions='[]';db.commit()
    for i,q in enumerate(snapshot):
        response=post(client,'/games/answer',{'session':row.id,'index':i,'choice':q['answer']})
        assert response.json()['correct'] is True
    assert post(client,'/games/answer',{'session':row.id,'index':0,'choice':0}).status_code==409
    result=post(client,'/games/results',{'result':{'game':'quiz','session':row.id,'score':0}}).json()
    assert result['state']['results'][0]['score']==5
    assert result['award']==0 and result['state']['balance']==0


def test_battle_uses_shared_curriculum_and_rejects_other_program(db,client,acct):
    first=add_content(db);future=add_content(db,2)
    host=db.query(MinarAccount).one();student=models.Student(full_name='Peer',phone1='+998000000000',is_active=True);db.add(student);db.flush()
    group=models.Group(name='Other program',stage='frontend',is_active=True);db.add(group);db.flush()
    db.add(models.GroupStudent(group_id=group.id,student_id=student.id))
    peer=MinarAccount(student_id=student.id,login_id='OTHERQA',password_hash='test',course='HTML',active_group_id=group.id);db.add(peer);db.commit()
    room=battles.create_room(db,host,'quiz')
    with pytest.raises(MinarError) as exc:battles.join_room(db,peer,room['code'])
    assert exc.value.status==409
    group.stage='foundation';db.commit()
    assert battles.join_room(db,peer,room['code'])['code']==room['code']
    questions=battles._match_questions(host.id,peer.id)
    assert len(questions)==5 and {q['contentId'] for q in questions}=={first.id}


def test_assessment_idempotency_and_current_group_validation(client,db,acct):
    c=add_content(db);a=db.query(MinarAccount).one()
    qs=study.questions_for(c,a.id);payload={'requestId':'learning-check-001','answers':[q['answer'] for q in qs]}
    first=post(client,f'/study/content/{c.id}/assess',payload).json()
    second=post(client,f'/study/content/{c.id}/assess',payload).json()
    assert first['score']==second['score']==100 and first['award']==second['award']==0
    db.query(models.GroupStudent).update({'left_at':tz.today()});db.commit()
    assert post(client,f'/study/content/{c.id}/assess',payload).status_code==404


def test_publishing_requires_a_real_crm_lesson(client,db,acct,metodist_token):
    payload={'title':'Detached','course':'Foundation','topic':'Test','body':'Body','published':True,
        'questions':[{'q':'Question','options':['Yes','No'],'answer':0}]}
    assert client.post('/space/admin/study/content',json=payload,headers=H(metodist_token)).status_code==400
    c=add_content(db);payload['lessonId']=c.lesson_id
    assert client.post('/space/admin/study/content',json=payload,headers=H(metodist_token)).status_code==200


def test_all_24_foundation_checks_have_unique_valid_answers():
    from backend.minar.foundation_checks import CHECKS, additions
    from backend.minar.seed_content import FOUNDATION
    assert len(CHECKS)==len(FOUNDATION)==24
    for n in range(1,25):
        rows=additions(n)
        assert len(rows)==4 and len({q['q'] for q in rows})==4
        for q in rows:
            assert len(set(q['options']))==3 and q['options'][q['answer']] and q['explain']


def test_learning_migration_is_idempotent_and_preserves_teacher_content(db, monkeypatch, metodist_token):
    import importlib
    migration=importlib.import_module('backend.alembic.versions.20261103a_group_learning')
    original=add_content(db);original.slug='foundation-1';original.questions=json.dumps(json.loads(original.questions)[:1])
    custom=add_content(db,2);custom.slug='foundation-2'
    teacher=db.query(models.User).first()
    custom.updated_by_id=teacher.id;custom.questions=json.dumps(json.loads(custom.questions)[:1])
    legacy=add_content(db,8,linked=False);legacy.course='HTML'
    db.commit()
    monkeypatch.setattr(migration.op, 'get_bind', lambda: db.connection())
    for _ in range(2):
        migration.upgrade();db.commit();db.expire_all()
        assert len(json.loads(original.questions))==5
        assert len(json.loads(custom.questions))==1 and custom.published
        assert legacy.published is False
