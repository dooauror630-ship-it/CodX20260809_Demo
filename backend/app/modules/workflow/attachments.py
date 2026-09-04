import hashlib
import uuid
from pathlib import Path
from flask import current_app, send_file
from werkzeug.utils import secure_filename
from ...core.errors import ApiError
from ...extensions import db
from ..farm.service import get_accessible_farm
from .models import Attachment

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf", "xlsx", "xls", "csv", "txt"}
MAX_BYTES = 10 * 1024 * 1024

def _root():
    root = Path(current_app.instance_path) / "attachments"
    root.mkdir(parents=True, exist_ok=True)
    return root

def save_attachment(file, farm_id, resource_type, resource_id, actor):
    get_accessible_farm(farm_id, actor)
    if not file or not file.filename:
        raise ApiError("请选择附件", 400, "ATTACHMENT_REQUIRED")
    original = secure_filename(file.filename)
    if not original or "." not in original or original.rsplit(".", 1)[1].lower() not in ALLOWED_EXTENSIONS:
        raise ApiError("附件类型不受支持", 400, "ATTACHMENT_TYPE_INVALID")
    data = file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ApiError("附件不能超过 10MB", 413, "ATTACHMENT_TOO_LARGE")
    digest = hashlib.sha256(data).hexdigest()
    stored = f"{uuid.uuid4().hex}.{original.rsplit('.', 1)[1].lower()}"
    (_root() / stored).write_bytes(data)
    attachment = Attachment(farm_id=farm_id, resource_type=resource_type, resource_id=resource_id, original_name=original, stored_name=stored, mime_type=file.mimetype or "application/octet-stream", size_bytes=len(data), sha256=digest, created_by_id=actor.id)
    db.session.add(attachment)
    db.session.commit()
    return attachment_payload(attachment)

def attachment_payload(item):
    return {"id": item.id, "farmId": item.farm_id, "resourceType": item.resource_type, "resourceId": item.resource_id, "fileName": item.original_name, "mimeType": item.mime_type, "sizeBytes": item.size_bytes, "sha256": item.sha256, "createdAt": item.created_at.isoformat() if item.created_at else None}

def list_attachments(farm_id, resource_type, resource_id, actor):
    get_accessible_farm(farm_id, actor)
    rows = db.session.query(Attachment).filter_by(farm_id=farm_id, resource_type=resource_type, resource_id=resource_id).order_by(Attachment.id.desc()).all()
    return {"items": [attachment_payload(row) for row in rows]}

def download_attachment(attachment_id, actor):
    item = db.session.get(Attachment, attachment_id)
    if not item:
        raise ApiError("附件不存在", 404, "ATTACHMENT_NOT_FOUND")
    get_accessible_farm(item.farm_id, actor)
    path = _root() / item.stored_name
    if not path.is_file():
        raise ApiError("附件文件不存在", 404, "ATTACHMENT_FILE_MISSING")
    return send_file(path, mimetype=item.mime_type, as_attachment=True, download_name=item.original_name)
