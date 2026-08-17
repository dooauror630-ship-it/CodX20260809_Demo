import secrets
from functools import wraps

from flask import g, request, session

from .errors import ApiError
from ..extensions import db


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def init_security(app):
    @app.before_request
    def prepare_request():
        g.request_id = request.headers.get("X-Request-ID") or secrets.token_hex(12)
        g.current_user = None

        user_id = session.get("user_id")
        if user_id:
            from ..modules.auth.models import User

            user = db.session.get(User, user_id)
            if user and user.is_active:
                g.current_user = user
            else:
                session.clear()

        if request.method in SAFE_METHODS or not request.path.startswith("/api/"):
            return None
        supplied = request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf_token", "")
        if not supplied or not expected or not secrets.compare_digest(supplied, expected):
            raise ApiError("请求安全校验失败，请刷新页面后重试", 403, "CSRF_INVALID")
        return None

    @app.after_request
    def add_response_headers(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        if request.path.startswith(("/api/auth/", "/api/v1/auth/")):
            response.headers["Cache-Control"] = "no-store"
        return response


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.current_user is None:
            raise ApiError("请先登录", 401, "AUTH_REQUIRED")
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.current_user is None:
            raise ApiError("请先登录", 401, "AUTH_REQUIRED")
        if g.current_user.role != "admin":
            raise ApiError("仅系统管理员可以执行此操作", 403, "ADMIN_REQUIRED")
        return view(*args, **kwargs)

    return wrapped
