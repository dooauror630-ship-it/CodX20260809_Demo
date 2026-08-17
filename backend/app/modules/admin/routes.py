from flask import Blueprint, g, request

from ...core.errors import success_response
from ...core.security import admin_required
from ..auth.schemas import parse_payload
from ..auth.service import user_payload
from .schemas import ResetPasswordPayload, UpdateUserPayload, UserListQuery
from .service import list_users, reset_user_password, update_user


admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/users")
@admin_required
def users():
    query = parse_payload(UserListQuery, request.args.to_dict(), "筛选条件格式错误")
    return success_response(list_users(query))


@admin_bp.patch("/users/<int:user_id>")
@admin_required
def edit_user(user_id):
    payload = parse_payload(
        UpdateUserPayload,
        request.get_json(silent=True),
        "用户信息格式错误",
        {
            "displayName": "姓名须为 2-20 个字符",
            "role": "用户身份无效",
            "isActive": "账号状态无效",
        },
    )
    user = update_user(user_id, payload, g.current_user)
    return success_response({"user": user_payload(user)}, "用户信息已更新")


@admin_bp.post("/users/<int:user_id>/password")
@admin_required
def reset_password(user_id):
    payload = parse_payload(
        ResetPasswordPayload,
        request.get_json(silent=True),
        "密码格式错误",
        {"password": "密码须为 8-64 位，且同时包含字母和数字"},
    )
    user = reset_user_password(user_id, payload.password)
    return success_response({"user": user_payload(user)}, "密码已重置")
