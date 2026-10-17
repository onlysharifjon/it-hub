"""Staff workflows for SPACE. Every mutation enforces role and student ownership."""
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import models, tz
from ..database import get_db
from .admin import staff_user, _bearer, _audit
from . import support, learning, notify, catalog as C
from .models import (MinarAccount, MinarContent, MinarGroupCourse, MinarRevision, MinarHelpThread,
    MinarHelpMessage, MinarProject, MinarAttachment, MinarResult, MinarStock)
from .errors import MinarError
router=APIRouter()


def educator(credentials=Depends(_bearer),db:Session=Depends(get_db)):
    from ..main import require_auth
    user=require_auth(credentials,db)
    if user.role not in ('admin','support_teacher','teacher'):raise HTTPException(403,'Bu bo‘lim ustoz va admin uchun')
    return user


def permitted_students(db,user):
    q=db.query(models.Student.id)
    if user.role=='teacher':
        q=q.join(models.GroupStudent,models.GroupStudent.student_id==models.Student.id).join(models.Group,models.Group.id==models.GroupStudent.group_id).filter(models.Group.teacher_id==user.id,models.GroupStudent.left_at.is_(None))
    return q


def account(db,user,aid):
    acc=db.query(MinarAccount).filter(MinarAccount.id==aid,MinarAccount.student_id.in_(permitted_students(db,user))).first()
    if not acc:raise MinarError(404,'Talaba topilmadi.')
    return acc


def content_dict(c):
    return {'id':c.id,'slug':c.slug,'lessonId':c.lesson_id,'course':c.course,'topic':c.topic,'title':c.title,
            'body':c.body,'video':c.video_url,'resource':c.resource_url,'exercise':c.exercise,
            'questions':json.loads(c.questions),'position':c.position,'published':c.published}

@router.get('/study/content')
def list_content(db:Session=Depends(get_db),user=Depends(educator)):
    return [content_dict(c) for c in db.query(MinarContent).order_by(MinarContent.course,MinarContent.position).all()]

@router.post('/study/content')
def save_content(payload:dict=Body(...),db:Session=Depends(get_db),user=Depends(staff_user)):
    cid=payload.get('id');c=db.query(MinarContent).filter_by(id=cid).first() if cid else None
    if cid and not c:raise MinarError(404,'Dars topilmadi.')
    course=payload.get('course')
    if course not in (*C.COURSES, 'Foundation', 'Scratch', 'AI Creator'):raise MinarError(400,'Kursni tanlang.')
    qs=payload.get('questions',[])
    if not isinstance(qs,list) or not 1<=len(qs)<=10:raise MinarError(400,'1–10 ta test savoli kiriting.')
    clean=[]
    for q in qs:
        opts=q.get('options') if isinstance(q,dict) else None
        if not isinstance(opts,list) or not 2<=len(opts)<=6 or type(q.get('answer')) is not int or not 0<=q['answer']<len(opts):
            raise MinarError(400,'Test varianti yoki javobi noto‘g‘ri.')
        clean.append({'q':support.text(q.get('q'),500),'options':[support.text(o,300) for o in opts],
                      'answer':q['answer'],'explain':support.text(q.get('explain',''),1000,False)})
    lid=payload.get('lessonId') or None
    if lid and not db.query(models.Lesson.id).filter_by(id=lid).first():raise MinarError(404,'CRM darsi topilmadi.')
    if not c:
        import uuid
        c=MinarContent(slug='custom-'+uuid.uuid4().hex);db.add(c)
    c.title=support.text(payload.get('title'),200);c.course=course;c.topic=support.text(payload.get('topic'),80)
    c.body=support.text(payload.get('body'),30000);c.exercise=support.text(payload.get('exercise',''),5000,False)
    c.video_url=learning._clean_link(payload.get('video'));c.resource_url=learning._clean_link(payload.get('resource'))
    c.lesson_id=lid;c.questions=json.dumps(clean,ensure_ascii=False);c.published=payload.get('published') is True
    position=payload.get('position',0)
    if type(position) is not int or not 0<=position<=10000:raise MinarError(400,'Tartib raqami noto‘g‘ri.')
    c.position=position;c.updated_at=datetime.utcnow();c.updated_by_id=user.id
    db.flush();_audit(db,user,'content_publish' if c.published else 'content_draft',None,{'content_id':c.id,'title':c.title})
    db.commit();return content_dict(c)

@router.get('/study/groups')
def groups(db:Session=Depends(get_db),user=Depends(staff_user)):
    maps={g.group_id:g.course for g in db.query(MinarGroupCourse).all()}
    return [{'id':g.id,'name':g.name,'course':maps.get(g.id) or C.default_course_for_stage(g.stage)} for g in db.query(models.Group).filter_by(is_active=True).order_by(models.Group.name).all()]

@router.put('/study/groups/{gid}')
def group_course(gid:int,payload:dict=Body(...),db:Session=Depends(get_db),user=Depends(staff_user)):
    if payload.get('course') not in C.COURSES:raise MinarError(400,'Kursni tanlang.')
    if not db.query(models.Group.id).filter_by(id=gid).first():raise MinarError(404,'Guruh topilmadi.')
    row=db.query(MinarGroupCourse).filter_by(group_id=gid).first()
    if not row:row=MinarGroupCourse(group_id=gid);db.add(row)
    row.course=payload['course'];_audit(db,user,'group_course',None,{'group_id':gid,'course':row.course});db.commit()
    return {'ok':True}

@router.get('/study/reviews')
def reviews(status:str='submitted',db:Session=Depends(get_db),user=Depends(educator)):
    q=db.query(models.HomeworkSubmission,models.Homework,models.Student,MinarAccount).join(models.Homework,models.Homework.id==models.HomeworkSubmission.homework_id).join(models.Student,models.Student.id==models.HomeworkSubmission.student_id).join(MinarAccount,MinarAccount.student_id==models.Student.id).filter(models.Student.id.in_(permitted_students(db,user)))
    if user.role=='teacher':q=q.join(models.Group,models.Group.id==models.Homework.group_id).filter(models.Group.teacher_id==user.id)
    if status!='all':q=q.filter(models.HomeworkSubmission.status==status)
    out=[]
    for sub,hw,st,acc in q.order_by(models.HomeworkSubmission.submitted_at.desc()).limit(100).all():
        rev=db.query(MinarRevision).filter_by(account_id=acc.id,homework_id=hw.id).order_by(MinarRevision.id.desc()).limit(20).all()
        out.append({'homeworkId':hw.id,'studentId':st.id,'accountId':acc.id,'student':st.full_name,'title':hw.lesson_title,
                    **learning._homework_dict(hw,sub),'revisions':[{'status':r.status,'at':tz.isoformat(r.created_at),**json.loads(r.payload)} for r in rev]})
    return out

@router.post('/study/reviews/{hid}/{aid}')
def review(hid:int,aid:int,payload:dict=Body(...),db:Session=Depends(get_db),user=Depends(educator)):
    from .. import main,schemas
    acc=account(db,user,aid);hw=main._homework_for_actor(db,hid,user)
    from ..wallet import lock
    lock(db,acc.student_id)
    db.query(MinarAccount).filter_by(id=aid).with_for_update().one()
    sub=db.query(models.HomeworkSubmission).filter_by(homework_id=hid,student_id=acc.student_id).with_for_update().first()
    if not sub:raise MinarError(404,'Javob topilmadi.')
    feedback=support.text(payload.get('comment',''),1000,False)
    status=payload.get('status')
    if status not in ('returned','graded'):raise MinarError(400,'Holat noto‘g‘ri.')
    rubric=payload.get('rubric',{})
    if not isinstance(rubric,dict) or any(type(rubric.get(k)) is not int or not 0<=rubric[k]<=5 for k in ('correctness','clarity','independence')):
        raise MinarError(400,'Har bir mezon 0–5 ball bo‘lsin.')
    grade=round(sum(rubric[k] for k in ('correctness','clarity','independence'))/15*100)
    db.add(MinarRevision(account_id=aid,homework_id=hid,status=status,staff_id=user.id,payload=json.dumps({'feedback':feedback,'rubric':rubric,'grade':grade})))
    if status=='returned':
        if not feedback:raise MinarError(400,'Qaytarish sababini yozing.')
        sub.status='returned';sub.teacher_comment=feedback;sub.graded_at=datetime.utcnow();sub.graded_by_id=user.id
        notify.to_account(db,aid,'homework','Vazifani to‘ldirib yuboring',feedback,'homework')
        _audit(db,user,'homework_return',aid,{'homework_id':hid});db.commit()
    else:
        try:grade_payload=schemas.HomeworkGrade(grade=grade,comment=feedback,coins=payload.get('coins',0))
        except Exception:raise MinarError(400,'Coin 0–20 oralig‘ida bo‘lsin.')
        main.grade_homework_submission(hid,acc.student_id,grade_payload,db,user)
    return {'ok':True,'grade':grade}

@router.get('/study/portfolio')
def portfolio(db:Session=Depends(get_db),user=Depends(educator)):
    rows=db.query(MinarProject,MinarAccount,models.Student).join(MinarAccount,MinarAccount.id==MinarProject.account_id).join(models.Student,models.Student.id==MinarAccount.student_id).filter(models.Student.id.in_(permitted_students(db,user))).order_by(MinarProject.id.desc()).limit(100).all()
    return [{**support.project_dict(p),'student':s.full_name,'accountId':a.id} for p,a,s in rows]

@router.post('/study/portfolio/{pid}')
def review_project(pid:int,payload:dict=Body(...),db:Session=Depends(get_db),user=Depends(educator)):
    p=db.query(MinarProject).filter_by(id=pid).with_for_update().first()
    if not p:raise MinarError(404,'Loyiha topilmadi.')
    account(db,user,p.account_id)
    if payload.get('status') not in ('approved','changes'):raise MinarError(400,'Holat noto‘g‘ri.')
    p.status=payload['status'];p.feedback=support.text(payload.get('feedback',''),2000,False);p.reviewed_by_id=user.id;p.updated_at=datetime.utcnow()
    if p.status!='approved':p.share_token=None
    notify.to_account(db,p.account_id,'system','Loyihangiz ko‘rib chiqildi',p.feedback,'portfolio')
    _audit(db,user,'portfolio_review',p.account_id,{'project_id':pid,'status':p.status});db.commit();return support.project_dict(p)

@router.get('/study/help')
def help_threads(db:Session=Depends(get_db),user=Depends(educator)):
    q=db.query(MinarHelpThread,models.Student.full_name).join(MinarAccount,MinarAccount.id==MinarHelpThread.account_id).join(models.Student,models.Student.id==MinarAccount.student_id).filter(models.Student.id.in_(permitted_students(db,user)))
    if user.role=='teacher':q=q.filter(MinarHelpThread.assigned_to_id==user.id)
    return [{**support.thread_dict(db,t),'student':name} for t,name in q.order_by(MinarHelpThread.updated_at.desc()).limit(100).all()]

@router.post('/study/help/{tid}')
def help_reply(tid:int,payload:dict=Body(...),db:Session=Depends(get_db),user=Depends(educator)):
    t=db.query(MinarHelpThread).filter_by(id=tid).first()
    if not t:raise MinarError(404,'Savol topilmadi.')
    account(db,user,t.account_id)
    if user.role=='teacher' and t.assigned_to_id!=user.id:raise MinarError(403,'Savol boshqa ustozga biriktirilgan.')
    status=payload.get('status','answered')
    if status not in ('open','answered','closed'):raise MinarError(400,'Holat noto‘g‘ri.')
    body=support.text(payload.get('body'),3000)
    db.add(MinarHelpMessage(thread_id=tid,staff_id=user.id,body=body));t.status=status;t.updated_at=datetime.utcnow()
    notify.to_account(db,t.account_id,'system','Ustoz savolingizga javob berdi',t.subject,'help')
    _audit(db,user,'mentor_reply',t.account_id,{'thread_id':tid,'status':status});db.commit();return support.thread_dict(db,t)

@router.get('/study/attachments/{aid}')
def download(aid:str,db:Session=Depends(get_db),user=Depends(educator)):
    row=db.query(MinarAttachment).filter_by(id=aid).first()
    if not row:raise MinarError(404,'Fayl topilmadi.')
    account(db,user,row.account_id);return support.file_response(row)

@router.get('/stock')
def stock(db:Session=Depends(get_db),user=Depends(staff_user)):
    stock={s.product_id:s.quantity for s in db.query(MinarStock).all()}
    return [{'id':pid,'name':p[0],'price':p[3],'quantity':stock.get(pid,0)} for pid,p in C.PRODUCTS.items() if p[1]=='space']

@router.put('/stock/{pid}')
def stock_update(pid:str,payload:dict=Body(...),db:Session=Depends(get_db),user=Depends(staff_user)):
    product=C.PRODUCTS.get(pid)
    if not product or product[1]!='space':raise MinarError(404,'Mahsulot topilmadi.')
    qty=payload.get('quantity')
    if type(qty)is not int or not 0<=qty<=100000:raise MinarError(400,'Qoldiq 0–100000 oralig‘ida bo‘lsin.')
    row=db.query(MinarStock).filter_by(product_id=pid).with_for_update().first()
    if not row:row=MinarStock(product_id=pid,quantity=0);db.add(row)
    old=row.quantity;row.quantity=qty;row.updated_at=datetime.utcnow()
    _audit(db,user,'stock_update',None,{'product_id':pid,'old':old,'quantity':qty});db.commit();return {'ok':True}

@router.get('/study/anomalies')
def anomalies(db:Session=Depends(get_db),user=Depends(staff_user)):
    lo=datetime.utcnow()-timedelta(days=7)
    rows=db.query(MinarResult.account_id,MinarResult.local_date,func.count(MinarResult.id)).filter(MinarResult.created_at>=lo).group_by(MinarResult.account_id,MinarResult.local_date).having(func.count(MinarResult.id)>50).all()
    return [{'accountId':aid,'date':day,'attempts':n,'reason':'Kuniga 50 dan ortiq o‘yin. Mukofot va XP limitlangan.'} for aid,day,n in rows]

@router.get('/study/lessons')
def lesson_choices(db:Session=Depends(get_db),user=Depends(staff_user)):
    return [{'id':l.id,'title':l.title,'category':l.category,'number':l.lesson_number} for l in db.query(models.Lesson).order_by(models.Lesson.category,models.Lesson.lesson_number).all()]
