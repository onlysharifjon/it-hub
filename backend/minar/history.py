"""Database pagination and totals over the complete wallet, never truncated UI data."""
from datetime import date
from sqlalchemy import select, union_all, literal, func, case
from .. import models, tz
from .models import MinarLedger, MinarResult
from .errors import MinarError


def listing(db, acc, offset=0, month=None):
    ct, ml = models.CoinTransaction, MinarLedger
    q = union_all(select(ct.id.label('id'), literal('crm').label('source'), ct.reason.label('title'),
            ct.amount, ct.created_at.label('created_at')).where(ct.student_id == acc.student_id),
        select(ml.id, literal('space'), ml.title, ml.amount, ml.created_at).where(ml.account_id == acc.id)).subquery()
    filters=[]
    if month:
        try:
            lo = date.fromisoformat(month+'-01')
            hi = date(lo.year+int(lo.month==12), lo.month%12+1, 1)
            filters = [q.c.created_at >= tz.day_bounds(lo)[0], q.c.created_at < tz.day_bounds(hi)[0]]
        except ValueError:
            raise MinarError(400, 'Oy YYYY-MM shaklida bo‘lsin.')
    total, earned, spent = db.query(func.count(), func.coalesce(func.sum(case((q.c.amount>0,q.c.amount),else_=0)),0),
        func.coalesce(func.sum(case((q.c.amount<0,-q.c.amount),else_=0)),0)).select_from(q).filter(*filters).one()
    rows=db.query(q).filter(*filters).order_by(q.c.created_at.desc(),q.c.source,q.c.id.desc()).offset(max(0,offset)).limit(50).all()
    return {'items':[{'id':f'{r.source}-{r.id}','title':r.title,'amount':r.amount,'time':tz.isoformat(r.created_at),
                     'date':tz.to_local(r.created_at).date().isoformat()} for r in rows],
            'total':total,'earned':int(earned),'spent':int(spent),'next':offset+50 if offset+50<total else None}


def game_listing(db,acc,offset=0,month=None):
    import json
    q=db.query(MinarResult).filter(MinarResult.account_id==acc.id)
    if month:
        try:date.fromisoformat(month+'-01')
        except ValueError:raise MinarError(400,'Oy YYYY-MM shaklida bo‘lsin.')
        q=q.filter(MinarResult.local_date.like(month+'-%'))
    total,xp,coins=q.with_entities(func.count(MinarResult.id),func.coalesce(func.sum(MinarResult.xp),0),func.coalesce(func.sum(MinarResult.award),0)).one()
    rows=q.order_by(MinarResult.created_at.desc(),MinarResult.id.desc()).offset(max(0,offset)).limit(50).all()
    return {'items':[{**json.loads(r.payload),'id':r.result_id,'date':r.local_date,'xp':r.xp,'award':r.award} for r in rows],
            'total':total,'xp':int(xp),'coins':int(coins),'next':offset+50 if offset+50<total else None}


def attendance_listing(db,acc,month=None,offset=0):
    q=db.query(models.Attendance,models.Group.name).join(models.Group,models.Group.id==models.Attendance.group_id).filter(models.Attendance.student_id==acc.student_id,models.Attendance.is_present.isnot(None))
    if month:
        try:
            lo=date.fromisoformat(month+'-01');hi=date(lo.year+int(lo.month==12),lo.month%12+1,1)
        except ValueError:raise MinarError(400,'Oy YYYY-MM shaklida bo‘lsin.')
        q=q.filter(models.Attendance.lesson_date>=lo,models.Attendance.lesson_date<hi)
    total,present=q.with_entities(func.count(models.Attendance.id),func.coalesce(func.sum(case((models.Attendance.is_present.is_(True),1),else_=0)),0)).one()
    rows=q.order_by(models.Attendance.lesson_date.desc(),models.Attendance.id.desc()).offset(max(0,offset)).limit(50).all()
    return {'items':[{'id':a.id,'date':a.lesson_date.isoformat(),'group':g,'status':'present' if a.is_present else 'absent'} for a,g in rows],
            'total':total,'present':int(present),'absent':total-int(present),'next':offset+50 if offset+50<total else None}
