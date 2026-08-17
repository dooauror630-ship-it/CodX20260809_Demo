from flask import Blueprint, g, request

from ...core.errors import success_response
from ...core.security import admin_required, login_required
from ..auth.schemas import parse_payload
from .schemas import CreateCropVarietyPayload, UpdateCropVarietyPayload
from .service import create_crop_variety, list_catalogs, update_crop_variety


catalog_bp = Blueprint("catalog", __name__)


@catalog_bp.get("/catalogs")
@login_required
def catalogs():
    return success_response(list_catalogs(g.current_user))


@catalog_bp.post("/crop-varieties")
@admin_required
def add_crop_variety():
    payload = parse_payload(CreateCropVarietyPayload, request.get_json(silent=True), "品种信息格式错误")
    return success_response(
        {"variety": create_crop_variety(payload, g.current_user)},
        "作物品种已创建",
        201,
    )


@catalog_bp.patch("/crop-varieties/<int:variety_id>")
@admin_required
def edit_crop_variety(variety_id):
    payload = parse_payload(UpdateCropVarietyPayload, request.get_json(silent=True), "品种信息格式错误")
    return success_response(
        {"variety": update_crop_variety(variety_id, payload, g.current_user)},
        "作物品种已更新",
    )
