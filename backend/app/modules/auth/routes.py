from flask import Blueprint, current_app, g, jsonify, request, session

from ...core.errors import ApiError
from ...core.security import csrf_token, login_required
from .schemas import LoginPayload, REGISTER_FIELD_MESSAGES, RegisterPayload, parse_payload
from .service import authenticate_user, register_user, user_payload


auth_bp = Blueprint("auth", __name__)


def auth_response(user=None, message=None, status=200):
    body = {
        "success": True,
        "requestId": g.request_id,
        "csrfToken": csrf_token(),
    }
    if user is not None:
        body["user"] = user_payload(user)
    if message:
        body["message"] = message
    return jsonify(body), status


@auth_bp.get("/csrf")
def get_csrf():
    return auth_response()


@auth_bp.post("/register")
def register():
    if not current_app.config["ALLOW_SELF_REGISTRATION"]:
        raise ApiError("当前系统已关闭公开注册", 403, "REGISTRATION_DISABLED")
    payload = parse_payload(
        RegisterPayload,
        request.get_json(silent=True),
        "注册信息格式错误",
        REGISTER_FIELD_MESSAGES,
    )
    user = register_user(payload)
    session.clear()
    session["user_id"] = user.id
    return auth_response(user, "注册成功", 201)


@auth_bp.post("/login")
def login():
    payload = parse_payload(LoginPayload, request.get_json(silent=True), "登录信息格式错误")
    user = authenticate_user(payload)
    session.clear()
    session["user_id"] = user.id
    session.permanent = payload.remember
    return auth_response(user, "登录成功")


@auth_bp.get("/me")
@login_required
def current_user():
    return auth_response(g.current_user)


@auth_bp.post("/logout")
@login_required
def logout():
    session.clear()
    return auth_response(message="已安全退出")
