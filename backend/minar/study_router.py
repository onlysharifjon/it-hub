import json
from typing import Optional
from fastapi import APIRouter, Depends, Body, UploadFile, File
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from . import auth, study, support
from .models import MinarAccount, MinarProgress, MinarAttachment, MinarProject
from .errors import MinarError

router=APIRouter()
Account=Depends(auth.current_account)

@router.get('/study/today')
def today(acc:MinarAccount=Account,db:Session=Depends(get_db)):
    return study.today(db,acc)

@router.post('/study/enrollment')
def enrollment(payload:dict=Body(...),acc:MinarAccount=Account,db:Session=Depends(get_db)):
    return study.select_group(db,acc,payload.get('groupId'))

@router.get('/study/content')
def content_list(acc:MinarAccount=Account,db:Session=Depends(get_db)):
    return study.contents(db,acc)

@router.get('/study/content/{cid}')
def content(cid:int,acc:MinarAccount=Account,db:Session=Depends(get_db)):
    c=study.content_for(db,acc,cid)
    p=db.query(MinarProgress).filter_by(account_id=acc.id,content_id=cid).first()
    return study.public_content(c,p,True,acc.id)

@router.post('/study/content/{cid}/assess')
def assess(cid:int,payload:dict=Body(...),acc:MinarAccount=Account,db:Session=Depends(get_db)):
    return study.assess(db,acc,cid,payload)

@router.get('/study/knowledge')
def knowledge(acc:MinarAccount=Account,db:Session=Depends(get_db)):
    return study.knowledge(db,acc)

@router.get('/homework/{hid}/draft')
def draft(hid:int,acc:MinarAccount=Account,db:Session=Depends(get_db)):
    return support.draft(db,acc,hid)

@router.put('/homework/{hid}/draft')
def save_draft(hid:int,payload:dict=Body(...),acc:MinarAccount=Account,db:Session=Depends(get_db)):
    return support.draft(db,acc,hid,payload)

@router.post('/attachments')
def upload(file:UploadFile=File(...),acc:MinarAccount=Account,db:Session=Depends(get_db)):
    return support.upload(db,acc,file)

@router.get('/attachments/{aid}')
def attachment(aid:str,acc:MinarAccount=Account,db:Session=Depends(get_db)):
    row=db.query(MinarAttachment).filter_by(id=aid,account_id=acc.id).first()
    if not row:raise MinarError(404,'Fayl topilmadi.')
    return support.file_response(row)

@router.get('/portfolio')
def portfolio(acc:MinarAccount=Account,db:Session=Depends(get_db)):
    return support.projects(db,acc)

@router.post('/portfolio')
def new_project(payload:dict=Body(...),acc:MinarAccount=Account,db:Session=Depends(get_db)):
    return support.save_project(db,acc,payload)

@router.put('/portfolio/{pid}')
def save_project(pid:int,payload:dict=Body(...),acc:MinarAccount=Account,db:Session=Depends(get_db)):
    return support.save_project(db,acc,payload,pid)

@router.post('/portfolio/{pid}/share')
def share(pid:int,payload:dict=Body(...),acc:MinarAccount=Account,db:Session=Depends(get_db)):
    return support.share_project(db,acc,pid,payload.get('enabled') is True)

@router.get('/public/portfolio/{token}')
def public_project(token:str,db:Session=Depends(get_db)):
    from fastapi.responses import HTMLResponse
    from html import escape
    p=db.query(MinarProject).join(MinarAccount,MinarAccount.id==MinarProject.account_id).filter(MinarProject.share_token==token,MinarProject.status=='approved',MinarAccount.is_active.is_(True)).first()
    if not p:raise MinarError(404,'Loyiha topilmadi.')
    # Explicit opt-in, teacher approval, no student personal data in the public page.
    html=f'<!doctype html><html lang="uz"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{escape(p.title)}</title><main><h1>{escape(p.title)}</h1><p>{escape(p.description)}</p><a href="{escape(p.url,quote=True)}" rel="noopener noreferrer">Loyihani ko‘rish</a><p>Minar Academy · Ustoz tasdiqlagan loyiha</p></main></html>'
    return HTMLResponse(html,headers={'Cache-Control':'no-store','X-Robots-Tag':'noindex','Content-Security-Policy':"default-src 'none'; base-uri 'none'; frame-ancestors 'none'"})

@router.get('/certificates/{cid}')
def certificate(cid:int,acc:MinarAccount=Account,db:Session=Depends(get_db)):
    from fastapi.responses import RedirectResponse, FileResponse
    from pathlib import Path
    import os
    c=db.query(models.Certificate).filter_by(id=cid,student_id=acc.student_id).first()
    if not c:raise MinarError(404,'Sertifikat topilmadi.')
    if c.file_url.startswith('/uploads/certificates/'):
        base=Path(os.getenv('UPLOAD_DIR','/app/uploads')).resolve()
        path=(base/c.file_url.removeprefix('/uploads/')).resolve()
        if base not in path.parents or not path.is_file():raise MinarError(404,'Fayl topilmadi.')
        return FileResponse(path,filename='sertifikat.pdf',headers={'Cache-Control':'no-store'})
    url=support.learning._clean_link(c.file_url)
    return RedirectResponse(url)

@router.get('/help')
def help_list(acc:MinarAccount=Account,db:Session=Depends(get_db)):
    return support.help_list(db,acc)

@router.post('/help')
def help_new(payload:dict=Body(...),acc:MinarAccount=Account,db:Session=Depends(get_db)):
    return support.help_send(db,acc,payload)

@router.post('/help/{tid}/messages')
def help_reply(tid:int,payload:dict=Body(...),acc:MinarAccount=Account,db:Session=Depends(get_db)):
    return support.help_send(db,acc,payload,tid)
