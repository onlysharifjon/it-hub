"""Student learning hub: enrollment, published content, assessment and spaced review."""
import json
import hashlib
import random
from datetime import datetime, timedelta
from sqlalchemy import func
from .. import models, tz, security, core_calc
from ..wallet import account_transaction
from . import learning, catalog as C
from .models import (MinarAccount, MinarGroupCourse, MinarContent, MinarProgress, MinarLearningAttempt,
                     MinarLedger, MinarRevision, MinarProject)
from .errors import MinarError


def enrollments(db, acc):
    groups = learning.active_groups(db, acc.student_id)
    mappings = {r.group_id:r.course for r in db.query(MinarGroupCourse).filter(MinarGroupCourse.group_id.in_([g.id for g in groups])).all()}
    selected = next((g for g in groups if g.id == acc.active_group_id), groups[0] if groups else None)
    changed = selected and selected.id != acc.active_group_id
    if selected:
        if changed and acc.active_group_id is not None:
            acc.course_override = None
        course = acc.course_override or mappings.get(selected.id) or (acc.course if acc.active_group_id is None or not changed else C.default_course_for_stage(selected.stage))
        if changed or acc.course != course:
            acc.active_group_id, acc.course = selected.id, course
            db.commit()
    return [{'id':g.id, 'name':g.name, 'course':course_name(g), 'stage':g.stage,
             'selected':g.id==acc.active_group_id} for g in groups]


def select_group(db, acc, group_id):
    groups = enrollments(db, acc)
    g = next((g for g in groups if g['id']==group_id), None)
    if not g:
        raise MinarError(404, 'Guruh topilmadi.')
    acc.course_override = None
    acc.active_group_id = g['id']
    db.commit()
    return {'ok':True}


def course_name(group):
    return group.course.name if group.course else {'foundation':'Foundation', 'frontend':'Frontend',
        'backend':'Backend', 'fullstack':'Fullstack'}.get(group.stage, group.stage or 'Guruh dasturi')


def learning_context(db, acc):
    groups = learning.active_groups(db, acc.student_id)
    group = next((g for g in groups if g.id == acc.active_group_id), groups[0] if groups else None)
    if not group:
        return None, 0, []
    completed = core_calc.group_completed_lessons(db, [group.id]).get(group.id, 0)
    lessons = db.query(models.Lesson).filter(models.Lesson.category == (group.stage or 'foundation')) \
        .order_by(models.Lesson.lesson_number).all()
    return group, completed, lessons


def visible_query(db, acc):
    # Only the selected CRM group's taught/current lessons. A legacy account
    # course string must never make unrelated global coding drills visible.
    group, completed, lessons = learning_context(db, acc)
    lesson_ids = [l.id for l in lessons if l.lesson_number <= completed + 1]
    return db.query(MinarContent).filter(MinarContent.published.is_(True),
        MinarContent.lesson_id.in_(lesson_ids))


def pathway(db, acc):
    groups = enrollments(db, acc)
    group, completed, lessons = learning_context(db, acc)
    content = contents(db, acc)
    by_lesson = {}
    for row in content:
        by_lesson.setdefault(row['lessonId'], []).append(row)
    current = next((l for l in lessons if l.lesson_number > completed), lessons[-1] if lessons else None)
    return {'groups':groups, 'groupId':group.id if group else None, 'group':group.name if group else None,
        'course':course_name(group) if group else None, 'completed':completed,
        'currentLessonId':current.id if current else None,
        'lessons':[{'id':l.id, 'number':l.lesson_number, 'title':l.title, 'section':l.section,
            'status':'done' if l.lesson_number <= completed else 'current' if l.id == current.id else 'upcoming',
            'content':by_lesson.get(l.id, [])} for l in lessons], 'content':content}


def quiz_questions(db, acc, seed, peer=None, count=5):
    rows = visible_query(db, acc).join(models.Lesson, MinarContent.lesson_id == models.Lesson.id) \
        .order_by(models.Lesson.lesson_number.desc(), MinarContent.position).all()
    if peer is not None:
        allowed = {c.id for c in visible_query(db, peer).all()}
        rows = [c for c in rows if c.id in allowed]
    rng = random.Random(seed)
    pool, seen = [], set()
    for c in rows:
        for q in json.loads(c.questions):
            if q['q'] in seen:
                continue
            seen.add(q['q'])
            pool.append({**q, 'code':None, 'topic':c.title, 'contentId':c.id})
        # Prefer the current topic; supplement only from earlier taught lessons.
        if len(pool) >= count:
            break
    if len(pool) < count:
        raise MinarError(409, 'Guruh mavzulari bo‘yicha kamida 5 ta savol tayyor bo‘lishi kerak. Kurslarim bo‘limini tekshir.')
    result=[]
    for q in rng.sample(pool, count):
        order=list(range(len(q['options'])));rng.shuffle(order)
        result.append({**q, 'options':[q['options'][i] for i in order], 'answer':order.index(q['answer'])})
    return result


def content_for(db, acc, cid):
    row = visible_query(db, acc).filter(MinarContent.id==cid).first()
    if not row:
        raise MinarError(404, 'Dars topilmadi yoki hali nashr qilinmagan.')
    return row


def questions_for(c, aid):
    seed=int.from_bytes(hashlib.sha256(f"{aid}:{c.id}:{c.updated_at}".encode()).digest()[:8],'big')
    rng=random.Random(seed);out=[]
    for q in json.loads(c.questions):
        order=list(range(len(q['options'])));rng.shuffle(order)
        out.append({**q,'options':[q['options'][i] for i in order],'answer':order.index(q['answer'])})
    return out


def public_content(c, p=None, full=False, aid=0):
    result={'id':c.id,'title':c.title,'course':c.course,'topic':c.topic,'lessonId':c.lesson_id,
        'score':p.last_score if p else None,'bestScore':p.best_score if p else 0,
        'questionCount':len(json.loads(c.questions)),
        'completed':bool(p and p.completed_at),'reviewDue':bool(p and p.next_review_at and p.next_review_at <= datetime.utcnow()),
        'nextReview':tz.isoformat(p.next_review_at) if p and p.next_review_at else None}
    if full:
        result.update(body=c.body,video=c.video_url,resource=c.resource_url,exercise=c.exercise,
            questions=[{'q':q['q'],'options':q['options']} for q in questions_for(c,aid)])
    return result


def contents(db, acc):
    enrollments(db, acc)
    progress = {p.content_id:p for p in db.query(MinarProgress).filter(MinarProgress.account_id==acc.id)}
    return [public_content(c,progress.get(c.id)) for c in visible_query(db,acc).order_by(MinarContent.course,MinarContent.position,MinarContent.id).all()]


def assess(db, acc, cid, payload):
    if not security.rate_limit_ok(f'minar-assess:{acc.id}', limit=20, window=600):
        raise MinarError(429,'Biroz mashq qilib, keyin qayta urinib ko‘r.')
    c = content_for(db,acc,cid)
    req=payload.get('requestId')
    if not isinstance(req,str) or not 8 <= len(req) <= 64:
        raise MinarError(400,'So‘rov identifikatori kerak.')
    with account_transaction(db,acc):
        prev=db.query(MinarLearningAttempt).filter_by(account_id=acc.id,request_id=req).first()
        if prev:
            if prev.content_id != cid:
                raise MinarError(409,'Bu so‘rov boshqa dars uchun ishlatilgan.')
            return {'score':prev.score,'passed':prev.score>=80,'mistakes':json.loads(prev.mistakes),'award':0}
        questions=questions_for(c,acc.id)
        answers=payload.get('answers')
        if not questions or not isinstance(answers,list) or len(answers)!=len(questions) or any(
                isinstance(a,bool) or not isinstance(a,int) or a<0 or a>=len(q['options']) for a,q in zip(answers,questions)):
            raise MinarError(400,'Barcha savollarga javob bering.')
        mistakes=[{'index':i,'explanation':q.get('explain','Mavzuni yana bir marta o‘qing.')} for i,(a,q) in enumerate(zip(answers,questions)) if a!=q['answer']]
        score=round(100*(len(questions)-len(mistakes))/len(questions));now=datetime.utcnow()
        p=db.query(MinarProgress).filter_by(account_id=acc.id,content_id=cid).first()
        if not p:
            p=MinarProgress(account_id=acc.id,content_id=cid,best_score=0,attempts=0,review_level=0)
            db.add(p)
        first=not p.completed_at
        due=bool(p.next_review_at and p.next_review_at<=now)
        p.last_score=score;p.best_score=max(p.best_score,score);p.attempts+=1;p.last_attempt_at=now
        award=0
        if score>=80:
            # When every available lesson is complete, daily practice remains possible
            # even between spaced-review dates. It never advances the review schedule.
            daily_practice = False
            if not first and not due:
                completed_ids = db.query(MinarProgress.content_id).filter(
                    MinarProgress.account_id == acc.id, MinarProgress.completed_at.isnot(None))
                daily_practice = visible_query(db, acc).filter(~MinarContent.id.in_(completed_ids)).first() is None
            if first or due:
                p.completed_at=p.completed_at or now
                p.review_level=min(4,p.review_level+1)
                p.next_review_at=now+timedelta(days=(1,3,7,14)[p.review_level-1])
                if first:
                    award=0
                    db.add(MinarLedger(account_id=acc.id,ref_key=f'study:{cid}',kind='lesson',title=c.title,amount=award,local_date=tz.today().isoformat()))
            if not first and (due or daily_practice):
                # One daily review credit qualifies the mission, with no repeat XP.
                ref=f'review:{tz.today().isoformat()}'
                if not db.query(MinarLedger.id).filter_by(account_id=acc.id,ref_key=ref).first():
                    award=0
                    db.add(MinarLedger(account_id=acc.id,ref_key=ref,kind='lesson',title='Bilimni takrorlash',amount=award,local_date=tz.today().isoformat()))
        else:
            p.next_review_at=now+timedelta(days=1)
        db.add(MinarLearningAttempt(account_id=acc.id,content_id=cid,request_id=req,score=score,mistakes=json.dumps(mistakes)))
        db.flush()
        from . import achievements
        achievements.evaluate(db, acc)
        db.commit()
        return {'score':score,'passed':score>=80,'mistakes':mistakes,'award':award}


def knowledge(db, acc):
    rows=contents(db,acc); topics={}
    for row in rows:
        key=(row['course'],row['topic'])
        t=topics.setdefault(key,{'course':key[0],'topic':key[1],'total':0,'completed':0,'scores':[],'review':[]})
        t['total']+=1;t['completed']+=int(row['completed']);t['scores'].append(row['score'] or 0)
        if row['reviewDue'] or (row['score'] is not None and row['score']<80):t['review'].append(row['id'])
    for t in topics.values():t['mastery']=round(sum(t.pop('scores'))/t['total'])
    mistakes=db.query(MinarLearningAttempt,MinarContent.title).join(MinarContent,MinarContent.id==MinarLearningAttempt.content_id).filter(MinarLearningAttempt.account_id==acc.id,MinarLearningAttempt.score<100).order_by(MinarLearningAttempt.id.desc()).limit(10).all()
    return {'topics':list(topics.values()),'mistakes':[{'title':title,'contentId':a.content_id,'items':json.loads(a.mistakes)} for a,title in mistakes]}


def today(db, acc):
    from ..parent.service import build_schedule
    student=db.query(models.Student).filter_by(id=acc.student_id).one()
    schedule=[s.dict() for s in build_schedule(db,student)]
    local=tz.to_local(datetime.utcnow())
    upcoming=[]
    for s in schedule:
        delta=(s['day_of_week']-local.isoweekday())%7
        if delta==0 and s['start_time']<local.strftime('%H:%M'):delta=7
        upcoming.append({**s,'date':(local.date()+timedelta(days=delta)).isoformat()})
    upcoming.sort(key=lambda s:(s['date'],s['start_time']))
    lessons=contents(db,acc)
    next_lesson=next((x for x in lessons if x['reviewDue']),None) or next((x for x in lessons if not x['completed']),None)
    if not next_lesson and lessons:
        next_lesson={**min(lessons,key=lambda x:x['score'] or 0),'dailyPractice':True}
    feedback=db.query(models.HomeworkSubmission,models.Homework.lesson_title).join(models.Homework,models.Homework.id==models.HomeworkSubmission.homework_id).filter(models.HomeworkSubmission.student_id==acc.student_id,models.HomeworkSubmission.teacher_comment.isnot(None)).order_by(models.HomeworkSubmission.graded_at.desc()).first()
    return {'nextLesson':upcoming[0] if upcoming else None,'schedule':schedule,'homework':learning.homework_list(db,acc,0,'pending'),
        'pendingCount':learning.pending_count(db,acc),'continue':next_lesson,'enrollments':enrollments(db,acc),
        'feedback':{'title':feedback[1],'comment':feedback[0].teacher_comment,'grade':feedback[0].grade} if feedback else None}
