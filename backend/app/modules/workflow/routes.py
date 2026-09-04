from flask import Blueprint, g, request
from ...core.errors import success_response
from ...core.security import login_required
from ..auth.schemas import parse_payload
from .schemas import CreateTaskPayload, TaskListQuery
from .service import create_task, complete_task, list_audits, list_tasks
from .attachments import download_attachment, list_attachments, save_attachment

workflow_bp = Blueprint("workflow", __name__)

@workflow_bp.get("/tasks")
@login_required
def tasks(): return success_response(list_tasks(parse_payload(TaskListQuery, request.args.to_dict(), "任务筛选条件格式错误"), g.current_user))

@workflow_bp.post("/tasks")
@login_required
def add_task():
    task, created = create_task(parse_payload(CreateTaskPayload, request.get_json(silent=True), "任务信息格式错误"), g.current_user)
    return success_response({"task": task}, "任务已创建" if created else "该任务已存在", 201 if created else 200)

@workflow_bp.post("/tasks/<int:task_id>/complete")
@login_required
def finish_task(task_id): return success_response({"task": complete_task(task_id, g.current_user)}, "任务已完成")

@workflow_bp.get("/audit-logs")
@login_required
def audits(): return success_response(list_audits(request.args.get("farmId", type=int), g.current_user))

@workflow_bp.post("/attachments")
@login_required
def upload_attachment():
    item = save_attachment(request.files.get("file"), request.form.get("farmId", type=int), request.form.get("resourceType", "GENERAL"), request.form.get("resourceId", type=int), g.current_user)
    return success_response({"attachment": item}, "附件已上传", 201)

@workflow_bp.get("/attachments")
@login_required
def attachments():
    return success_response(list_attachments(request.args.get("farmId", type=int), request.args.get("resourceType", "GENERAL"), request.args.get("resourceId", type=int), g.current_user))

@workflow_bp.get("/attachments/<int:attachment_id>/download")
@login_required
def attachment_download(attachment_id): return download_attachment(attachment_id, g.current_user)
