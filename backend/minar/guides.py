"""Superadmin-only guide reader, legacy files and operational status."""
import json
import os
import time
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from .admin import staff_user
router=APIRouter()
DOCS=Path(__file__).with_name('docs')
FILES={'space-guide.pdf':('SPACE: admin, ustoz va o‘quvchi yo‘riqnomasi','application/pdf'),
       'space-guide.html':('SPACE yo‘riqnomasi — HTML','text/html'),
       'space-changes.pdf':('Audit bo‘yicha bajarilgan ishlar hisoboti','application/pdf')}
CONTENTS={'space-guide.pdf':'space-guide.json','space-guide.html':'space-guide.json',
          'space-changes.pdf':'space-changes.json'}
def superadmin(user=Depends(staff_user)):
    if user.role!='admin':raise HTTPException(403,'Faqat superadmin uchun')
    return user
@router.get('/guides')
def guides(user=Depends(superadmin)):
    return [{'id':k,'title':v[0],'format':k.rsplit('.',1)[1].upper(),'size':(DOCS/k).stat().st_size if (DOCS/k).is_file() else 0} for k,v in FILES.items()]
@router.get('/guides/{name}/content')
def guide_content(name:str,user=Depends(superadmin)):
    filename=CONTENTS.get(name)
    if not filename or not (DOCS/filename).is_file():
        raise HTTPException(404,'Yo‘riqnoma topilmadi')
    return JSONResponse(json.loads((DOCS/filename).read_text(encoding='utf-8')),
                        headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
@router.get('/guides/{name}')
def download(name:str,user=Depends(superadmin)):
    if name not in FILES or not (DOCS/name).is_file():raise HTTPException(404,'Yo‘riqnoma topilmadi')
    return FileResponse(DOCS/name,media_type=FILES[name][1],filename=name,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
@router.get('/system-status')
def system_status(user=Depends(superadmin)):
    from ..readiness import check
    monitor=None
    try:
        monitor=json.loads(Path(os.getenv('MONITOR_STATUS_PATH','/var/www/it-hub/data/monitor/status.json')).read_text()[:50000])
        monitor['stale']=time.time()-monitor.get('checkedAt',0)>180
    except (OSError,ValueError):pass
    return {'readiness':json.loads(check().body),'monitor':monitor,'aiConfigured':bool(os.getenv('ANTHROPIC_API_KEY','').strip()),'release':'SPACE audit 2026-10-18'}
