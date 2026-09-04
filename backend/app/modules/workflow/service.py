import json
from datetime import datetime
from sqlalchemy import select
from ...core.errors import ApiError
from ...extensions import db
from ..farm.service import get_accessible_farm
from ..inventory.purchase_service import _require_write_access
from .models import AuditLog, FarmTask

def _payload(task):
    return {"id": task.id, "farmId": task.farm_id, "taskNo": task.task_no, "title": task.title, "dueDate": task.due_date.isoformat(), "status": task.status, "notes": task.notes, "createdAt": task.created_at.isoformat() if task.created_at else None, "completedAt": task.completed_at.isoformat() if task.completed_at else None}

def _audit(farm_id, actor_id, action, resource_type, resource_id, detail=None):
    db.session.add(AuditLog(farm_id=farm_id, actor_id=actor_id, action=action, resource_type=resource_type, resource_id=resource_id, detail=json.dumps(detail, ensure_ascii=False) if detail else None))

def list_tasks(query, actor):
    get_accessible_farm(query.farm_id, actor)
    stmt = select(FarmTask).where(FarmTask.farm_id == query.farm_id)
    if query.status != "all":
        stmt = stmt.where(FarmTask.status == query.status.upper())
    return {"items": [_payload(t) for t in db.session.scalars(stmt.order_by(FarmTask.due_date, FarmTask.id)).all()]}

def create_task(payload, actor):
    _require_write_access(payload.farm_id, actor)
    existing = db.session.scalar(select(FarmTask).where(FarmTask.farm_id == payload.farm_id, FarmTask.task_no == payload.task_no))
    if existing:
        return _payload(existing), False
    task = FarmTask(farm_id=payload.farm_id, task_no=payload.task_no, title=payload.title, due_date=payload.due_date, notes=payload.notes, created_by_id=actor.id)
    db.session.add(task)
    db.session.flush()
    _audit(payload.farm_id, actor.id, "CREATE", "FARM_TASK", task.id, {"taskNo": task.task_no})
    db.session.commit()
    return _payload(task), True

def complete_task(task_id, actor):
    task = db.session.get(FarmTask, task_id)
    if not task:
        raise ApiError("任务不存在", 404, "TASK_NOT_FOUND")
    _require_write_access(task.farm_id, actor)
    if task.status == "DONE":
        return _payload(task)
    task.status, task.completed_by_id, task.completed_at = "DONE", actor.id, datetime.now()
    _audit(task.farm_id, actor.id, "COMPLETE", "FARM_TASK", task.id)
    db.session.commit()
    return _payload(task)

def list_audits(farm_id, actor):
    get_accessible_farm(farm_id, actor)
    rows = db.session.scalars(select(AuditLog).where(AuditLog.farm_id == farm_id).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(200)).all()
    return {"items": [{"id": r.id, "farmId": r.farm_id, "actorId": r.actor_id, "action": r.action, "resourceType": r.resource_type, "resourceId": r.resource_id, "detail": r.detail, "createdAt": r.created_at.isoformat() if r.created_at else None} for r in rows]}
