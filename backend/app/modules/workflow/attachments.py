import hashlib
import uuid
from pathlib import Path
from flask import current_app, send_file
from werkzeug.utils import secure_filename
from ...core.errors import ApiError
from ...extensions import db
from ..farm.service import get_accessible_farm
from ..farm.models import Farm
from ..inventory.models import InventoryCount, PurchaseOrder, Warehouse, Item
from ..trade.models import Payment, SalesOrder, SalesReturn
from ..crop.models import CropCycle, FieldOperation, HarvestBatch, TobaccoCuringBatch, GradingRecord
from ..livestock.models import LivestockBatch
from .models import Attachment

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf", "xlsx", "xls", "csv", "txt"}
MAX_BYTES = 10 * 1024 * 1024
RESOURCE_MODELS = {
    "TASK": "farm_task",
    "PURCHASE_ORDER": PurchaseOrder,
    "SALES_ORDER": SalesOrder,
    "SALES_RETURN": SalesReturn,
    "PAYMENT": Payment,
    "INVENTORY_COUNT": InventoryCount,
    "CROP_CYCLE": CropCycle,
    "FIELD_OPERATION": FieldOperation,
    "HARVEST_BATCH": HarvestBatch,
    "TOBACCO_CURING_BATCH": TobaccoCuringBatch,
    "GRADING_RECORD": GradingRecord,
    "LIVESTOCK_BATCH": LivestockBatch,
    "WAREHOUSE": Warehouse,
    "ITEM": Item,
}

def _root():
    root = Path(current_app.instance_path) / "attachments"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _validate_resource(farm_id, resource_type, resource_id):
    resource_type = (resource_type or "GENERAL").strip().upper()
    if resource_type == "GENERAL":
        if resource_id is not None:
            raise ApiError("通用附件不能绑定资源编号", 400, "ATTACHMENT_RESOURCE_INVALID")
        return resource_type
    if resource_type == "FARM":
        if resource_id != farm_id or db.session.get(Farm, resource_id) is None:
            raise ApiError("附件资源不属于当前农场", 409, "ATTACHMENT_RESOURCE_MISMATCH")
        return resource_type
    model = RESOURCE_MODELS.get(resource_type)
    if model is None or resource_id is None or resource_id <= 0:
        raise ApiError("附件资源类型或编号无效", 400, "ATTACHMENT_RESOURCE_INVALID")
    if model == "farm_task":
        from .models import FarmTask

        resource = db.session.get(FarmTask, resource_id)
    else:
        resource = db.session.get(model, resource_id)
    if resource is None or getattr(resource, "farm_id", None) != farm_id:
        raise ApiError("附件资源不属于当前农场", 409, "ATTACHMENT_RESOURCE_MISMATCH")
    return resource_type

def save_attachment(file, farm_id, resource_type, resource_id, actor):
    get_accessible_farm(farm_id, actor)
    resource_type = _validate_resource(farm_id, resource_type, resource_id)
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
    resource_type = _validate_resource(farm_id, resource_type, resource_id)
    rows = db.session.query(Attachment).filter_by(farm_id=farm_id, resource_type=resource_type, resource_id=resource_id).order_by(Attachment.id.desc()).all()
    return {"items": [attachment_payload(row) for row in rows]}

def download_attachment(attachment_id, actor):
    item = db.session.get(Attachment, attachment_id)
    if not item:
        raise ApiError("附件不存在", 404, "ATTACHMENT_NOT_FOUND")
    get_accessible_farm(item.farm_id, actor)
    root = _root().resolve()
    stored_name = Path(item.stored_name)
    # 数据库值即使被篡改，也不能跳出附件根目录或指向嵌套路径。
    if stored_name.name != item.stored_name or "\x00" in item.stored_name:
        raise ApiError("附件文件路径无效", 400, "ATTACHMENT_PATH_INVALID")
    path = (root / stored_name).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ApiError("附件文件路径无效", 400, "ATTACHMENT_PATH_INVALID") from error
    if not path.is_file():
        raise ApiError("附件文件不存在", 404, "ATTACHMENT_FILE_MISSING")
    return send_file(path, mimetype=item.mime_type, as_attachment=True, download_name=item.original_name)
