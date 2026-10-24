"""Server-authoritative assessments, bilingual library and learning practice."""
import hashlib
import json
import random
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, Body, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_
from .. import models, tz, security
from ..database import get_db
from ..wallet import account_transaction
from . import auth, notify, support
from .models import MinarAccount, MinarLedger
from .academy_models import AcademyTopic as Topic, AcademyAssignment as Assignment, AcademyAttempt as Attempt, AcademyPractice as Practice, AcademyBonus as Bonus, AcademyNotice as Notice
from .staff_study import educator, permitted_students
from .admin import staff_user, _audit
from .errors import MinarError

router = APIRouter()
staff = APIRouter()
Account = Depends(auth.current_account)

def pack(v): return json.dumps(v, ensure_ascii=False)
def stamp(v): return v.replace(tzinfo=timezone.utc).isoformat() if v else None
def integer(v, lo, hi):
    if type(v) is not int or not lo <= v <= hi: raise MinarError(400, f'Qiymat {lo}–{hi} oralig‘ida bo‘lsin.')
    return v

def date(v):
    try:
        parsed=datetime.fromisoformat(v.replace('Z','+00:00'))
        if parsed.tzinfo is None: raise ValueError('timezone required')
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, AttributeError, TypeError): raise MinarError(400,'Sana va vaqtni vaqt mintaqasi bilan kiriting.')

def groups(db, acc):
    return db.query(models.GroupStudent.group_id).join(models.Group,models.Group.id==models.GroupStudent.group_id).filter(models.GroupStudent.student_id==acc.student_id, models.GroupStudent.left_at.is_(None),models.Group.is_active.is_(True))

def assignments(db, acc, include_closed=False):
    query=db.query(Assignment).filter(Assignment.group_id.in_(groups(db,acc)))
    return query if include_closed else query.filter(Assignment.active.is_(True))

def staff_assignments(db,user):
    q=db.query(Assignment)
    if user.role=='teacher': q=q.filter((Assignment.created_by==user.id) | Assignment.group_id.in_(db.query(models.Group.id).filter_by(teacher_id=user.id)))
    return q

def permitted_assignment(db,user,aid,lock=False):
    query=staff_assignments(db,user).filter(Assignment.id==aid)
    # NO KEY UPDATE serializes start/close while allowing notification inserts
    # to check their foreign key without reversing the wallet lock order.
    if lock:query=query.populate_existing().with_for_update(key_share=True)
    a=query.first()
    if not a: raise MinarError(404,'Test topilmadi.')
    return a

def visible_topics(db,acc):
    return db.query(Topic).filter(Topic.published.is_(True),Topic.id.in_(assignments(db,acc,include_closed=True).with_entities(Assignment.topic_id)))

def topic_dict(t,language='uz',full=False):
    d=json.loads(t.data)
    result={'id':t.id,'slug':t.slug,'course':t.course,'title':d.get('title_ru') or t.title if language=='ru' else t.title,'topic':d.get('topic',''),'published':t.published,'questionCount':len(d['questions']),'hasRussian':bool(d.get('body_ru')),'hasSlides':bool(d.get('slides'))}
    if full: result.update(body=(d.get('body_ru') or d['body']) if language=='ru' else d['body'],exercise=d.get('exercise',''),resources=d.get('resources',''))
    return result

def question_public(q,language='uz'):
    return {'id':q['id'],'q':(q.get('q_ru') or q['q']) if language=='ru' else q['q'],'options':(q.get('options_ru') or q['options']) if language=='ru' else q['options'],'image':q.get('image','')}

def shuffled(q):
    q=dict(q);order=list(range(len(q['options'])));random.SystemRandom().shuffle(order)
    q['options']=[q['options'][i] for i in order]
    if q.get('options_ru'): q['options_ru']=[q['options_ru'][i] for i in order]
    q['answer']=order.index(q['answer']);return q

def assignment_dict(a):
    return {'id':a.id,'topicId':a.topic_id,'title':a.title,'groupId':a.group_id,'count':a.count,'minutes':a.minutes,'maxAttempts':a.max_attempts,'startsAt':stamp(a.starts_at),'dueAt':stamp(a.due_at),'active':a.active,'publicToken':a.public_token}

def attempt_dict(a,teacher=False):
    qs=json.loads(a.snapshot);answers=json.loads(a.answers)
    result={'id':a.id,'assignmentId':a.assignment_id,'deadline':stamp(a.deadline),'serverTime':stamp(datetime.utcnow()),'finishedAt':stamp(a.finished_at),'score':a.score,'language':a.language,'answers':answers,'warnings':a.warnings,'questions':[question_public(q,a.language) for q in qs]}
    if a.finished_at:
        result['review']=[{'id':q['id'],'picked':answers.get(q['id']),'correct':answers.get(q['id'])==q['answer'],**({'answer':q['answer']} if teacher else {})} for q in qs]
    if teacher: result.update(student=a.guest_name,phone=a.guest_phone,accountId=a.account_id,leadId=a.lead_id)
    return result

def award(db,acc,ref,amount,title):
    if not db.query(MinarLedger.id).filter_by(account_id=acc.id,ref_key=ref).first():
        db.add(MinarLedger(account_id=acc.id,ref_key=ref,amount=amount,kind='lesson',title=title,local_date=tz.today().isoformat()))
        return amount
    return 0

def finish(db,a):
    if a.finished_at: return
    qs=json.loads(a.snapshot);answers=json.loads(a.answers)
    a.score=round(100*sum(answers.get(q['id'])==q['answer'] for q in qs)/len(qs));a.finished_at=datetime.utcnow()
    assignment=db.get(Assignment,a.assignment_id)
    if a.account_id:
        acc=db.get(MinarAccount,a.account_id)
        for q in qs:
            if answers.get(q['id'])==q['answer']: continue
            m=db.query(Practice).filter_by(account_id=a.account_id,topic_id=assignment.topic_id,question_id=q['id']).first()
            if not m: m=Practice(account_id=a.account_id,topic_id=assignment.topic_id,question_id=q['id']);db.add(m)
            m.snapshot=pack(q);m.streak=0;m.resolved_at=None
        if a.score>=80: award(db,acc,f'academy-pass:{assignment.topic_id}',5,'Mavzu testi o‘zlashtirildi')
    db.flush()

def new_attempt(db,a,acc=None,language='uz',guest=None):
    now=datetime.utcnow()
    if not a.active or a.starts_at>now or (a.due_at is not None and now>=a.due_at): raise MinarError(409,'Test hali boshlanmagan yoki yakunlangan.')
    topic=db.get(Topic,a.topic_id)
    if not topic or not topic.published: raise MinarError(404,'Mavzu hali nashr qilinmagan.')
    q=db.query(Attempt).filter_by(assignment_id=a.id)
    q=q.filter_by(account_id=acc.id) if acc else q.filter_by(guest_phone=guest['phone'])
    old=q.order_by(Attempt.started_at.desc()).first()
    if old and not old.finished_at:
        if old.deadline>now:
            if not acc and old.guest_key!=guest['key']: raise MinarError(409,'Test avval boshqa brauzerda boshlangan.')
            return old
        finish(db,old)
    if q.count()>=a.max_attempts: raise MinarError(409,'Ruxsat etilgan urinishlar tugadi.')
    pool=json.loads(topic.data)['questions']
    if len(pool)<a.count:raise MinarError(409,'Savollar banki o‘zgargan. Ustoz test savollari sonini yangilashi kerak.')
    # Half of a retake prioritizes previously missed questions.
    missed=[]
    if old:
        previous=json.loads(old.answers)
        wrong={x['id'] for x in json.loads(old.snapshot) if previous.get(x['id'])!=x['answer']}
        missed=[x for x in pool if x['id'] in wrong]
    rng=random.SystemRandom();selected=rng.sample(missed,min(len(missed),a.count//2))
    chosen={x['id'] for x in selected};selected+=rng.sample([x for x in pool if x['id'] not in chosen],min(a.count,len(pool))-len(selected));rng.shuffle(selected)
    deadline=now+timedelta(minutes=a.minutes)
    if a.due_at is not None:deadline=min(deadline,a.due_at)
    row=Attempt(id=str(uuid4()),assignment_id=a.id,account_id=acc.id if acc else None,language='ru' if language=='ru' else 'uz',snapshot=pack([shuffled(x) for x in selected]),deadline=deadline,answers='{}')
    if guest: row.guest_name=guest['name'];row.guest_phone=guest['phone'];row.guest_key=guest['key']
    db.add(row);db.flush();return row

def save_answers(db,a,payload,submit=False):
    if a.finished_at: return attempt_dict(a)
    if datetime.utcnow()>=a.deadline or not db.get(Assignment,a.assignment_id).active:
        finish(db,a);db.commit();return attempt_dict(a)
    qs={q['id']:q for q in json.loads(a.snapshot)};incoming=payload.get('answers',{})
    if not isinstance(incoming,dict) or len(incoming)>len(qs): raise MinarError(400,'Javoblar noto‘g‘ri.')
    for key,value in incoming.items():
        if key not in qs: raise MinarError(400,'Savol topilmadi.')
        integer(value,0,len(qs[key]['options'])-1)
    a.answers=pack({**json.loads(a.answers),**incoming})
    a.warnings=max(a.warnings,integer(payload.get('warnings',a.warnings),0,10000))
    if submit: finish(db,a)
    db.commit();return attempt_dict(a)

@router.get('/academy')
def dashboard(db:Session=Depends(get_db),acc:MinarAccount=Account):
    tick(db,acc)
    rows=assignments(db,acc,include_closed=True).order_by(Assignment.id.desc()).limit(200).all()
    attempts=db.query(Attempt).filter_by(account_id=acc.id).order_by(Attempt.started_at.desc()).limit(300).all()
    return {'assignments':[{**assignment_dict(a),'attempts':[{'id':x.id,'score':x.score,'finishedAt':stamp(x.finished_at)} for x in attempts if x.assignment_id==a.id]} for a in rows], 'topics':[topic_dict(t) for t in visible_topics(db,acc).all()], 'mistakes':db.query(Practice).filter_by(account_id=acc.id,resolved_at=None).count()}

@router.get('/academy/topics/{tid}')
def topic_read(tid:int,language:str='uz',db:Session=Depends(get_db),acc:MinarAccount=Account):
    t=visible_topics(db,acc).filter(Topic.id==tid).first()
    if not t: raise MinarError(404,'Mavzu topilmadi.')
    return topic_dict(t,language,True)

@router.post('/academy/assignments/{aid}/start')
def start(aid:int,payload:dict=Body(...),db:Session=Depends(get_db),acc:MinarAccount=Account):
    # Starting and staff closure lock the assignment before any wallet rows.
    # A concurrent start cannot slip in after the staff member closes the test.
    a=assignments(db,acc).filter(Assignment.id==aid).populate_existing().with_for_update(key_share=True).first()
    if not a: raise MinarError(404,'Test topilmadi.')
    with account_transaction(db,acc):
        row=new_attempt(db,a,acc,payload.get('language'));db.commit();return attempt_dict(row)

def own_attempt(db,acc,key):
    a=db.query(Attempt).filter_by(id=key,account_id=acc.id).first()
    if not a: raise MinarError(404,'Natija topilmadi.')
    return a

@router.get('/academy/attempts/{key}')
def resume(key:str,db:Session=Depends(get_db),acc:MinarAccount=Account):
    with account_transaction(db,acc):
        a=own_attempt(db,acc,key)
        if not a.finished_at and (a.deadline<=datetime.utcnow() or not db.get(Assignment,a.assignment_id).active): finish(db,a);db.commit()
        return attempt_dict(a)

@router.post('/academy/attempts/{key}')
def answer(key:str,payload:dict=Body(...),db:Session=Depends(get_db),acc:MinarAccount=Account):
    with account_transaction(db,acc):return save_answers(db,own_attempt(db,acc,key),payload,payload.get('submit') is True)

@router.get('/academy/practice')
def practice(language:str='uz',db:Session=Depends(get_db),acc:MinarAccount=Account):
    rows=db.query(Practice).filter_by(account_id=acc.id,resolved_at=None).order_by(Practice.last_answer_at,Practice.id).all()
    return {'remaining':len(rows),'items':[{'id':m.id,'topicId':m.topic_id,'streak':m.streak,'availableAt':stamp(m.last_answer_at+timedelta(seconds=10)) if m.last_answer_at else None,'question':question_public(json.loads(m.snapshot),language)} for m in rows[:30]]}

@router.post('/academy/practice/{mid}')
def practice_answer(mid:int,payload:dict=Body(...),db:Session=Depends(get_db),acc:MinarAccount=Account):
    with account_transaction(db,acc):
        m=db.query(Practice).filter_by(id=mid,account_id=acc.id).first()
        if not m or m.resolved_at: raise MinarError(409,'Bu xato allaqachon tuzatilgan.')
        if m.last_answer_at and datetime.utcnow()-m.last_answer_at<timedelta(seconds=10): raise MinarError(429,'Savolni qayta o‘ylab ko‘ring. 10 soniyadan keyin urinishingiz mumkin.')
        q=json.loads(m.snapshot);correct=integer(payload.get('answer'),0,len(q['options'])-1)==q['answer']
        m.streak=m.streak+1 if correct else 0;m.last_answer_at=datetime.utcnow();coins=0
        if m.streak>=3:
            m.resolved_at=datetime.utcnow()
            if not m.rewarded: coins=award(db,acc,f'academy-fix:{m.id}',2,'Xato ustida ishlash');m.rewarded=True
        db.commit();return {'correct':correct,'remaining':max(0,3-m.streak),'award':coins,'resolved':bool(m.resolved_at)}

@router.get('/academy/bonus')
def bonus(language:str='uz',db:Session=Depends(get_db),acc:MinarAccount=Account):
    with account_transaction(db,acc):
        day=tz.today().isoformat();q=db.query(Bonus).filter_by(account_id=acc.id,day=day)
        rows=q.all();done=sum(x.answered_at is not None for x in rows)
        pending=next((x for x in rows if not x.answered_at),None)
        if not pending and done<10:
            used={x.question_id for x in rows};pool=[]
            studied=db.query(Assignment.topic_id).join(Attempt,Attempt.assignment_id==Assignment.id).filter(Attempt.account_id==acc.id,Attempt.finished_at.isnot(None))
            for t in visible_topics(db,acc).filter(Topic.id.in_(studied)).all():
                pool.extend((t.id,x) for x in json.loads(t.data)['questions'] if x['id'] not in used)
            if pool:
                tid,question=random.SystemRandom().choice(pool)
                pending=Bonus(id=str(uuid4()),account_id=acc.id,topic_id=tid,question_id=question['id'],day=day,snapshot=pack(shuffled(question)))
                db.add(pending);db.commit()
        return {'done':done,'limit':10,'id':pending.id if pending else None,'question':question_public(json.loads(pending.snapshot),language) if pending else None}

@router.post('/academy/bonus/{bid}')
def bonus_answer(bid:str,payload:dict=Body(...),db:Session=Depends(get_db),acc:MinarAccount=Account):
    with account_transaction(db,acc):
        b=db.query(Bonus).filter_by(id=bid,account_id=acc.id,day=tz.today().isoformat()).first()
        if not b:raise MinarError(404,'Savol muddati tugagan.')
        if b.answered_at:return {'correct':b.correct,'award':0}
        q=json.loads(b.snapshot);b.correct=integer(payload.get('answer'),0,len(q['options'])-1)==q['answer'];b.answered_at=datetime.utcnow()
        coins=award(db,acc,'academy-bonus:'+b.id,1,'Kunlik bilim mashqi') if b.correct else 0
        db.commit();return {'correct':b.correct,'award':coins}

def tick(db,acc):
    """Idempotent scheduled-release notices and once-only overdue reminders."""
    with account_transaction(db,acc):
        now=datetime.utcnow()
        for a in assignments(db,acc).filter(Assignment.starts_at<=now,or_(Assignment.due_at.is_(None),Assignment.due_at>now)).all():
            done=db.query(Attempt.id).filter_by(assignment_id=a.id,account_id=acc.id).first()
            for kind,ready in [('assigned',True),('reminder',not done and now>=a.starts_at+timedelta(hours=3))]:
                if ready and not db.query(Notice.id).filter_by(assignment_id=a.id,account_id=acc.id,kind=kind).first():
                    db.add(Notice(assignment_id=a.id,account_id=acc.id,kind=kind))
                    notify.to_account(db,acc.id,'system','Yangi test' if kind=='assigned' else 'Testni bajarishni unutmang',a.title,'academy')
        closed=db.query(Assignment.id).filter(Assignment.active.is_(False))
        for a in db.query(Attempt).filter(Attempt.account_id==acc.id,Attempt.finished_at.is_(None),or_(Attempt.deadline<=now,Attempt.assignment_id.in_(closed))).all():finish(db,a)
        db.commit()

@staff.get('/academy/library')
def library(db:Session=Depends(get_db),user=Depends(educator)):
    installed={t.slug:t for t in db.query(Topic).all()}
    bundled=json.loads((Path(__file__).parent/'academy_data/library.json').read_text())
    return [{'slug':d['slug'],'title':d['title'],'course':d['course'],'questionCount':len(d['questions']),'hasRussian':bool(d.get('body_ru')),'hasSlides':bool(d.get('slides')),'id':installed[d['slug']].id if d['slug'] in installed else None,'published':installed[d['slug']].published if d['slug'] in installed else False} for d in bundled]+[topic_dict(t) for t in installed.values() if not t.slug.startswith('mywebsite-')]

@staff.post('/academy/import')
def import_library(payload:dict=Body(...),db:Session=Depends(get_db),user=Depends(staff_user)):
    slugs=payload.get('slugs',[])
    if not isinstance(slugs,list) or not slugs or len(slugs)>100 or not all(isinstance(x,str) for x in slugs):raise MinarError(400,'Mavzularni belgilang.')
    bundled=json.loads((Path(__file__).parent/'academy_data/library.json').read_text());items=[d for d in bundled if d['slug'] in slugs]
    if len(items)!=len(set(slugs)):raise MinarError(400,'Noma’lum mavzu.')
    added=0
    for d in items:
        t=db.query(Topic).filter_by(slug=d['slug']).first()
        if not t:db.add(Topic(slug=d['slug'],course=d['course'],title=d['title'],data=pack(d),published=False));added+=1
    _audit(db,user,'academy_import',None,{'count':added});db.commit();return {'added':added,'skipped':len(items)-added}

@staff.get('/academy/topics/{tid}')
def edit_topic(tid:int,db:Session=Depends(get_db),user=Depends(educator)):
    t=db.get(Topic,tid)
    if not t:raise MinarError(404,'Mavzu topilmadi.')
    return {**topic_dict(t),'data':json.loads(t.data)}

@staff.post('/academy/topics/{tid}')
def update_topic(tid:int,payload:dict=Body(...),db:Session=Depends(get_db),user=Depends(staff_user)):
    t=db.get(Topic,tid)
    if not t:raise MinarError(404,'Mavzu topilmadi.')
    data=payload.get('data',json.loads(t.data))
    if not isinstance(data,dict):raise MinarError(400,'Mavzu noto‘g‘ri.')
    qs=data.get('questions')
    if not isinstance(qs,list) or not 1<=len(qs)<=200:raise MinarError(400,'1–200 ta savol kiriting.')
    seen=set()
    for q in qs:
        if not isinstance(q,dict):raise MinarError(400,'Savol noto‘g‘ri.')
        q['id']=support.text(q.get('id'),100)
        if q['id'] in seen:raise MinarError(400,'Savol ID takrorlandi.')
        seen.add(q['id']);q['q']=support.text(q.get('q'),5000)
        opts=q.get('options')
        if not isinstance(opts,list) or not 2<=len(opts)<=6:raise MinarError(400,'2–6 ta variant kiriting.')
        q['options']=[support.text(o,2000) for o in opts];integer(q.get('answer'),0,len(opts)-1)
        if q.get('options_ru') and (not isinstance(q['options_ru'],list) or len(q['options_ru'])!=len(opts)):raise MinarError(400,'Tarjimadagi variantlar soni mos emas.')
        q['options_ru']=[support.text(o,2000) for o in q.get('options_ru',[])];q['q_ru']=support.text(q.get('q_ru',''),5000,False)
        if q.get('image'):q['image']=support.learning._clean_link(q['image'])
    for key,limit in [('title',250),('body',60000),('title_ru',250),('body_ru',60000),('slides',60000),('exercise',10000),('resources',10000)]:data[key]=support.text(data.get(key,''),limit,key in ('title','body'))
    t.title=data['title'];t.data=pack(data);t.published=payload.get('published') is True;t.updated_at=datetime.utcnow()
    _audit(db,user,'academy_topic_update',None,{'topic_id':tid,'published':t.published});db.commit();return topic_dict(t)

@staff.get('/academy/groups')
def staff_groups(db:Session=Depends(get_db),user=Depends(educator)):
    q=db.query(models.Group).filter_by(is_active=True)
    if user.role=='teacher':q=q.filter_by(teacher_id=user.id)
    return [{'id':g.id,'name':g.name} for g in q.order_by(models.Group.name).all()]

@staff.get('/academy/assignments')
def staff_list(db:Session=Depends(get_db),user=Depends(educator)):
    return [assignment_dict(a) for a in staff_assignments(db,user).order_by(Assignment.id.desc()).limit(300).all()]

@staff.post('/academy/assignments')
def assign(payload:dict=Body(...),db:Session=Depends(get_db),user=Depends(educator)):
    t=db.get(Topic,integer(payload.get('topicId'),1,2147483647))
    if not t or not t.published:raise MinarError(400,'Avval mavzuni nashr qiling.')
    public=payload.get('public') is True;gid=None if public else integer(payload.get('groupId'),1,2147483647)
    if gid:
        g=db.query(models.Group).filter_by(id=gid,is_active=True).first()
        if not g or (user.role=='teacher' and g.teacher_id!=user.id):raise MinarError(403,'Bu guruh sizga biriktirilmagan.')
    start=date(payload['startsAt']) if payload.get('startsAt') else datetime.utcnow()
    due=date(payload['dueAt']) if payload.get('dueAt') else None
    if due is not None and (due<=max(start,datetime.utcnow()) or due>datetime.utcnow()+timedelta(days=366)):raise MinarError(400,'Test muddatini tekshiring.')
    row=Assignment(topic_id=t.id,group_id=gid,created_by=user.id,title=support.text(payload.get('title') or t.title,250),count=integer(payload.get('count',10),1,min(100,len(json.loads(t.data)['questions']))),minutes=integer(payload.get('minutes',15),1,180),max_attempts=integer(payload.get('maxAttempts',2),1,5),starts_at=start,due_at=due,public_token=secrets.token_urlsafe(24) if public else None)
    db.add(row);db.flush();_audit(db,user,'academy_assign',None,{'assignment_id':row.id});db.commit();return assignment_dict(row)

@staff.post('/academy/assignments/{aid}/status')
def assignment_status(aid:int,payload:dict=Body(...),db:Session=Depends(get_db),user=Depends(educator)):
    if type(payload.get('active')) is not bool:raise MinarError(400,'Test holatini tanlang.')
    a=permitted_assignment(db,user,aid,lock=True)
    a.active=payload['active'];finished=0
    if a.active:
        # Reopening an older scheduled test makes it manually controlled too.
        a.due_at=None
    else:
        # Lock wallets in a stable order. Answers submitted before a wallet is
        # locked are included; later submissions receive the immutable result.
        rows=db.query(Attempt.id,Attempt.account_id).filter_by(assignment_id=a.id,finished_at=None).order_by(Attempt.account_id,Attempt.id).all()
        for key,account_id in rows:
            if account_id is not None:
                acc=db.get(MinarAccount,account_id)
                with account_transaction(db,acc):
                    attempt=db.query(Attempt).filter_by(id=key).populate_existing().with_for_update().one()
                    if not attempt.finished_at:finish(db,attempt);finished+=1
            else:
                attempt=db.query(Attempt).filter_by(id=key).populate_existing().with_for_update().one()
                if not attempt.finished_at:finish(db,attempt);finished+=1
    _audit(db,user,'academy_assignment_status',None,{'assignment_id':aid,'active':a.active,'finished_attempts':finished})
    db.commit();return {**assignment_dict(a),'finishedAttempts':finished}

@staff.get('/academy/report')
def report(assignmentId:int=0,db:Session=Depends(get_db),user=Depends(educator)):
    allowed=staff_assignments(db,user).with_entities(Assignment.id)
    q=db.query(Attempt).filter(Attempt.assignment_id.in_(allowed))
    if assignmentId:q=q.filter_by(assignment_id=assignmentId)
    rows=q.order_by(Attempt.started_at.desc()).limit(1000).all();questions={};students={};today=tz.today();daily=[]
    names=dict(db.query(MinarAccount.id,models.Student.full_name).join(models.Student,models.Student.id==MinarAccount.student_id).filter(models.Student.id.in_(permitted_students(db,user))).all())
    for a in rows:
        if not a.finished_at:continue
        if tz.to_local(a.finished_at).date()==today:daily.append(a.score)
        if a.account_id:students.setdefault(a.account_id,[]).append(a.score)
        answers=json.loads(a.answers)
        for item in json.loads(a.snapshot):
            stat=questions.setdefault(item['id'],{'id':item['id'],'q':item['q'],'total':0,'correct':0,'wrongOptions':{}});stat['total']+=1
            chosen=answers.get(item['id'])
            if chosen==item['answer']:stat['correct']+=1
            elif chosen is not None:
                label=item['options'][chosen];stat['wrongOptions'][label]=stat['wrongOptions'].get(label,0)+1
    for s in questions.values():s['percent']=round(100*s['correct']/s['total']);s['quality']='qiyin' if s['total']>=5 and s['percent']<30 else 'oson' if s['total']>=5 and s['percent']>=95 else 'normal'
    local_midnight=datetime.combine(today,datetime.min.time())-timedelta(hours=5)
    daily_query=q.filter(Attempt.finished_at>=local_midnight,Attempt.finished_at<local_midnight+timedelta(days=1))
    completed,average,below=daily_query.with_entities(func.count(Attempt.id),func.avg(Attempt.score),func.sum(case((Attempt.score<50,1),else_=0))).one()
    risk=[]
    for aid,scores in students.items():
        avg=round(sum(scores[:3])/len(scores[:3]))
        if avg<60:risk.append({'accountId':aid,'student':names.get(aid,'O‘quvchi'),'average':avg,'reason':'Oxirgi testlarda 60% dan past natija'})
    # Compact list; full immutable answer snapshots load only when requested.
    return {'attempts':[{'id':a.id,'assignmentId':a.assignment_id,'student':names.get(a.account_id,a.guest_name or 'O‘quvchi'),'phone':a.guest_phone,'accountId':a.account_id,'leadId':a.lead_id,'score':a.score,'finishedAt':stamp(a.finished_at),'warnings':a.warnings} for a in rows],
            'questions':sorted(questions.values(),key=lambda x:x['percent']), 'atRisk':risk,
            'total':q.count(),'analysisLimit':1000,
            'daily':{'date':today.isoformat(),'completed':completed,'average':round(average) if average is not None else None,'below50':below or 0}}

@staff.get('/academy/attempts/{key}')
def staff_attempt(key:str,db:Session=Depends(get_db),user=Depends(educator)):
    row=db.query(Attempt).filter(Attempt.id==key,Attempt.assignment_id.in_(staff_assignments(db,user).with_entities(Assignment.id))).first()
    if not row:raise MinarError(404,'Test natijasi topilmadi.')
    result=attempt_dict(row,True)
    if row.account_id:
        name=db.query(models.Student.full_name).join(MinarAccount,MinarAccount.student_id==models.Student.id).filter(MinarAccount.id==row.account_id).scalar()
        result['student']=name or 'O‘quvchi'
    return result


# Public entry tests carry a separate, opaque browser credential; never an account session.
def public_assignment(db,token,include_closed=False,lock=False):
    query=db.query(Assignment).filter_by(public_token=token)
    if not include_closed:query=query.filter_by(active=True)
    if lock:query=query.populate_existing().with_for_update(key_share=True)
    a=query.first()
    if not a:raise MinarError(404,'Havola topilmadi yoki yopilgan.')
    return a

def public_rate(request):
    auth.check_origin(request)
    host=auth.client_ip(request)
    if not security.rate_limit_ok('academy-public:'+host,limit=30,window=600):raise MinarError(429,'Juda ko‘p urinish. Keyinroq qayting.')

@router.get('/academy/public/{token}')
def public_info(token:str,db:Session=Depends(get_db)):
    a=public_assignment(db,token);return {k:v for k,v in assignment_dict(a).items() if k not in ('groupId','publicToken')}

@router.post('/academy/public/{token}/start')
def public_start(token:str,request:Request,response:Response,payload:dict=Body(...),db:Session=Depends(get_db)):
    public_rate(request);a=public_assignment(db,token,lock=True)
    name=support.text(payload.get('name'),120);phone=''.join(c for c in str(payload.get('phone','')) if c.isdigit())
    if not 9<=len(phone)<=15 or len(name)<3 or payload.get('consent') is not True:raise MinarError(400,'Ism, telefon va rozilikni kiriting.')
    raw=request.cookies.get('academy_guest_'+str(a.id)) or secrets.token_urlsafe(32)
    key=hashlib.sha256(raw.encode()).hexdigest()
    row=new_attempt(db,a,language=payload.get('language'),guest={'name':name,'phone':phone,'key':key});db.commit()
    response.set_cookie('academy_guest_'+str(a.id),raw,httponly=True,secure=auth.COOKIE_SECURE,samesite='lax',max_age=86400,path='/')
    response.headers['Cache-Control']='no-store';return attempt_dict(row)

@router.post('/academy/public/{token}/attempts/{key}')
def public_answer(token:str,key:str,request:Request,payload:dict=Body(...),db:Session=Depends(get_db)):
    auth.check_origin(request)
    a=public_assignment(db,token,include_closed=True)
    raw=request.cookies.get('academy_guest_'+str(a.id),'')
    row=db.query(Attempt).filter_by(id=key,assignment_id=a.id,guest_key=hashlib.sha256(raw.encode()).hexdigest()).with_for_update().first()
    if not raw or not row:raise MinarError(404,'Test shu brauzerda boshlanmagan.')
    return save_answers(db,row,payload,payload.get('submit') is True)

@staff.post('/academy/attempts/{key}/lead')
def link_lead(key:str,db:Session=Depends(get_db),user=Depends(staff_user)):
    row=db.query(Attempt).filter_by(id=key).with_for_update().first()
    if not row or row.account_id or not row.finished_at:raise MinarError(404,'Kirish testi natijasi topilmadi.')
    if row.lead_id:return {'leadId':row.lead_id}
    phone_key=row.guest_phone[-9:]
    lead=db.query(models.Lead).filter(models.Lead.phone_key==phone_key).first()
    if not lead:
        assignment=db.get(Assignment,row.assignment_id)
        lead=models.Lead(full_name=row.guest_name,phone='+'+row.guest_phone,phone_key=phone_key,created_by_id=user.id,status='new',notes=f'SPACE kirish testi: {assignment.title}. Natija: {row.score}%.',is_shared=True)
        db.add(lead);db.flush()
    row.lead_id=lead.id;_audit(db,user,'academy_lead_link',None,{'attempt_id':key,'lead_id':lead.id});db.commit();return {'leadId':lead.id}


def scheduled_tick():
    """Called by the existing CRM minute scheduler. No external messaging."""
    import logging
    from ..database import SessionLocal
    db=SessionLocal()
    try:
        ids=[x[0] for x in db.query(MinarAccount.id).filter_by(is_active=True).all()]
        for aid in ids:
            tick(db,db.get(MinarAccount,aid))
        now=tz.to_local(datetime.utcnow())
        closed=db.query(Assignment.id).filter(Assignment.active.is_(False))
        for guest in db.query(Attempt).filter(Attempt.account_id.is_(None),Attempt.finished_at.is_(None),or_(Attempt.deadline<=datetime.utcnow(),Attempt.assignment_id.in_(closed))).with_for_update().all():
            finish(db,guest)
        db.commit()
        if now.hour>=20:
            # Lock recipients so multiple scheduler workers cannot duplicate a digest.
            users=db.query(models.User).filter(models.User.id.in_(db.query(Assignment.created_by))).all()
            for user in users:
                db.query(models.User).filter_by(id=user.id).with_for_update().one()
                title='SPACE kun yakuni · '+now.date().isoformat()
                if not db.query(models.Notification.id).filter_by(user_id=user.id,notification_type='academy_daily',title=title).first():
                    stats=report(0,db,user)['daily']
                    db.add(models.Notification(user_id=user.id,notification_type='academy_daily',title=title,body=f"{stats['completed']} ta test. O‘rtacha: {stats['average'] if stats['average'] is not None else '—'}%. 50% dan past: {stats['below50']}.",link='#space_study'))
                db.commit()
    except Exception:
        db.rollback();logging.getLogger(__name__).exception('SPACE assessment scheduler failed')
    finally:db.close()

@staff.get('/academy/library/{slug}')
def preview_library(slug:str,user=Depends(educator)):
    data=json.loads((Path(__file__).parent/'academy_data/library.json').read_text())
    item=next((d for d in data if d['slug']==slug),None)
    if not item:raise MinarError(404,'Mavzu topilmadi.')
    return item

@staff.post('/academy/topics')
def create_topic(payload:dict=Body(...),db:Session=Depends(get_db),user=Depends(staff_user)):
    title=support.text(payload.get('title'),250);course=support.text(payload.get('course'),80)
    d={'title':title,'course':course,'body':'Dars materialini kiriting.','questions':[{'id':str(uuid4()),'q':'Savol matni','options':['Birinchi variant','Ikkinchi variant'],'answer':0}]}
    t=Topic(slug='custom-'+str(uuid4()),course=course,title=title,data=pack(d),published=False);db.add(t);db.flush()
    _audit(db,user,'academy_topic_create',None,{'topic_id':t.id});db.commit();return {'id':t.id}

@router.get('/academy/summary')
def summary(db:Session=Depends(get_db),acc:MinarAccount=Account):
    tick(db,acc)
    now=datetime.utcnow()
    completed=db.query(Attempt.assignment_id).filter(Attempt.account_id==acc.id,Attempt.finished_at.isnot(None))
    pending=assignments(db,acc).filter(Assignment.starts_at<=now,or_(Assignment.due_at.is_(None),Assignment.due_at>now),~Assignment.id.in_(completed)).order_by(Assignment.starts_at,Assignment.id).all()
    results=db.query(Attempt.score).filter(Attempt.account_id==acc.id,Attempt.finished_at.isnot(None)).order_by(Attempt.finished_at.desc()).limit(10).all()
    return {'pending':len(pending),'next':assignment_dict(pending[0]) if pending else None,'mistakes':db.query(Practice.id).filter_by(account_id=acc.id,resolved_at=None).count(),'recentAverage':round(sum(x[0] for x in results)/len(results)) if results else None}
