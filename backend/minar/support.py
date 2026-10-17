"""Private drafts, attachments, mentoring and reviewed student portfolio."""
import json
import os
import re
import secrets
import uuid
from datetime import datetime
from pathlib import Path
from fastapi.responses import FileResponse
from sqlalchemy import func
from .. import models, tz, security
from . import learning, notify
from .models import (MinarAccount, MinarDraft, MinarRevision, MinarAttachment, MinarProject,
                     MinarHelpThread, MinarHelpMessage)
from .errors import MinarError


def text(value, limit, required=True):
    if not isinstance(value,str) or len(value)>limit or (required and not value.strip()):
        raise MinarError(400,f'Matn 1–{limit} belgidan iborat bo‘lsin.')
    return value.strip()


def homework_for(db,acc,hid):
    hw=db.query(models.Homework).filter_by(id=hid).first()
    if not hw or hw.group_id not in {g.id for g in learning.active_groups(db,acc.student_id)}:
        raise MinarError(404,'Uy vazifasi topilmadi.')
    return hw


def attachment_ids(db,acc,ids):
    if not isinstance(ids,list) or len(ids)>5 or any(not isinstance(i,str) for i in ids):
        raise MinarError(400,'Ko‘pi bilan 5 ta fayl biriktiring.')
    found=db.query(MinarAttachment.id).filter(MinarAttachment.account_id==acc.id,MinarAttachment.id.in_(ids)).all()
    if {x[0] for x in found}!=set(ids):raise MinarError(404,'Fayl topilmadi.')
    return list(dict.fromkeys(ids))


def clean_draft(db,acc,payload):
    return {'answer':text(payload.get('answer',''),5000,False),'link':learning._clean_link(payload.get('link')),
            'attachments':attachment_ids(db,acc,payload.get('attachments',[]))}


def draft(db,acc,hid,payload=None):
    homework_for(db,acc,hid)
    if payload is not None:
        db.query(MinarAccount.id).filter_by(id=acc.id).with_for_update().one()
    row=db.query(MinarDraft).filter_by(account_id=acc.id,homework_id=hid).first()
    if payload is not None:
        if not row:row=MinarDraft(account_id=acc.id,homework_id=hid);db.add(row)
        row.payload=json.dumps(clean_draft(db,acc,payload));row.updated_at=datetime.utcnow();db.commit()
    revisions=db.query(MinarRevision).filter_by(account_id=acc.id,homework_id=hid).order_by(MinarRevision.id.desc()).limit(50).all()
    return {'draft':json.loads(row.payload) if row else None,'updatedAt':tz.isoformat(row.updated_at) if row else None,
            'revisions':[{'id':r.id,'status':r.status,'at':tz.isoformat(r.created_at),**json.loads(r.payload)} for r in revisions]}


def upload(db,acc,file):
    if not security.rate_limit_ok(f'minar-upload:{acc.id}',limit=20,window=3600):raise MinarError(429,'Fayl yuklash limiti tugadi.')
    data=file.file.read(5*1024*1024+1)
    if not data or len(data)>5*1024*1024:raise MinarError(400,'Fayl 5 MB dan oshmasin.')
    db.query(MinarAccount.id).filter_by(id=acc.id).with_for_update().one()
    total=db.query(func.coalesce(func.sum(MinarAttachment.size),0)).filter_by(account_id=acc.id).scalar()
    if total+len(data)>100*1024*1024:raise MinarError(400,'Fayllar uchun 100 MB limit tugadi. Ustozga murojaat qiling.')
    mime='application/pdf' if data.startswith(b'%PDF-') else 'image/png' if data.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if data.startswith(b'\xff\xd8\xff') else None
    if not mime:raise MinarError(400,'Faqat PDF, PNG va JPG qabul qilinadi.')
    aid=str(uuid.uuid4());rel='space-private/'+aid
    folder=Path(os.getenv('UPLOAD_DIR','/app/uploads'));(folder/'space-private').mkdir(parents=True,exist_ok=True)
    (folder/rel).write_bytes(data)
    row=MinarAttachment(id=aid,account_id=acc.id,name=Path(file.filename or 'fayl').name[:200],mime=mime,size=len(data),path=rel)
    db.add(row)
    try:db.commit()
    except Exception:
        (folder/rel).unlink(missing_ok=True);raise
    return {'id':row.id,'name':row.name,'size':row.size}


def file_response(row):
    path=Path(os.getenv('UPLOAD_DIR','/app/uploads'))/row.path
    if not path.is_file():raise MinarError(404,'Fayl topilmadi.')
    return FileResponse(path,media_type=row.mime,filename=row.name,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; sandbox"})


def project_dict(p):
    return {'id':p.id,'title':p.title,'description':p.description,'url':p.url,'status':p.status,
            'feedback':p.feedback,'shareToken':p.share_token,'createdAt':tz.isoformat(p.created_at)}


def projects(db,acc):
    rows=db.query(MinarProject).filter_by(account_id=acc.id).order_by(MinarProject.id.desc()).limit(100).all()
    certificates=db.query(models.Certificate).filter_by(student_id=acc.student_id).order_by(models.Certificate.id.desc()).all()
    return {'items':[project_dict(p) for p in rows],
        'certificates':[{'id':c.id,'title':c.title,'date':c.issued_at.isoformat() if c.issued_at else None} for c in certificates]}


def save_project(db,acc,payload,pid=None):
    if not security.rate_limit_ok(f'minar-project:{acc.id}',limit=20,window=3600):raise MinarError(429,'Biroz kuting.')
    p=db.query(MinarProject).filter_by(id=pid,account_id=acc.id).with_for_update().first() if pid else None
    if pid and not p:raise MinarError(404,'Loyiha topilmadi.')
    if not p:p=MinarProject(account_id=acc.id);db.add(p)
    p.title=text(payload.get('title'),120);p.description=text(payload.get('description'),3000)
    p.url=learning._clean_link(payload.get('url'))
    if not p.url:raise MinarError(400,'Loyiha havolasini kiriting.')
    p.status='pending';p.share_token=None;p.feedback=None;p.updated_at=datetime.utcnow();db.commit()
    return project_dict(p)


def share_project(db,acc,pid,enabled):
    p=db.query(MinarProject).filter_by(id=pid,account_id=acc.id).with_for_update().first()
    if not p:raise MinarError(404,'Loyiha topilmadi.')
    if enabled and p.status!='approved':raise MinarError(409,'Avval ustoz tasdiqlashi kerak.')
    p.share_token=(p.share_token or secrets.token_urlsafe(24)) if enabled else None
    db.commit();return project_dict(p)


def thread_dict(db,t):
    messages=db.query(MinarHelpMessage).filter_by(thread_id=t.id).order_by(MinarHelpMessage.id).limit(200).all()
    teacher=db.query(models.User).filter_by(id=t.assigned_to_id).first() if t.assigned_to_id else None
    return {'id':t.id,'subject':t.subject,'status':t.status,'groupId':t.group_id,'homeworkId':t.homework_id,'contentId':t.content_id,
            'teacher':getattr(teacher,'full_name',None) or getattr(teacher,'username',None),
            'messages':[{'id':m.id,'staff':bool(m.staff_id),'body':m.body,'attachments':json.loads(m.attachments),'at':tz.isoformat(m.created_at)} for m in messages]}


def help_list(db,acc):
    return [thread_dict(db,t) for t in db.query(MinarHelpThread).filter_by(account_id=acc.id).order_by(MinarHelpThread.updated_at.desc()).limit(50).all()]


def help_send(db,acc,payload,tid=None):
    if not security.rate_limit_ok(f'minar-help:{acc.id}',limit=20,window=3600):raise MinarError(429,'Biroz kuting.')
    if tid:
        t=db.query(MinarHelpThread).filter_by(id=tid,account_id=acc.id).first()
        if not t:raise MinarError(404,'Savol topilmadi.')
    else:
        groups=learning.active_groups(db,acc.student_id)
        group=next((g for g in groups if g.id==payload.get('groupId')),None) or next((g for g in groups if g.id==acc.active_group_id),None)
        if not group:raise MinarError(400,'Faol guruhni tanlang.')
        hid=payload.get('homeworkId');cid=payload.get('contentId')
        if hid and homework_for(db,acc,hid).group_id!=group.id:raise MinarError(400,'Vazifa boshqa guruhga tegishli.')
        if cid:
            from .study import content_for
            content_for(db,acc,cid)
        t=MinarHelpThread(account_id=acc.id,group_id=group.id,subject=text(payload.get('subject'),120),homework_id=hid,content_id=cid,assigned_to_id=group.teacher_id)
        db.add(t);db.flush()
    t.status='open';t.updated_at=datetime.utcnow()
    db.add(MinarHelpMessage(thread_id=t.id,body=text(payload.get('body'),3000),attachments=json.dumps(attachment_ids(db,acc,payload.get('attachments',[])))))
    if t.assigned_to_id:
        db.add(models.Notification(user_id=t.assigned_to_id,notification_type='homework',title='SPACE: yangi savol',body=t.subject,link='/space_study',is_read=False))
    db.commit();return thread_dict(db,t)
