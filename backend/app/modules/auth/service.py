from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ...core.errors import ApiError
from ...extensions import db
from .models import User
from .schemas import LoginPayload, RegisterPayload


SHANGHAI_TIMEZONE = timezone(timedelta(hours=8))


def find_user_by_username(username):
    statement = select(User).where(func.lower(User.username) == username.lower())
    return db.session.execute(statement).scalar_one_or_none()


def register_user(payload: RegisterPayload):
    if find_user_by_username(payload.username):
        raise ApiError("该账号已被注册", 409, "USERNAME_EXISTS", "username")

    user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=generate_password_hash(payload.password),
        role="operator",
    )
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该账号已被注册", 409, "USERNAME_EXISTS", "username") from error
    return user


def ensure_admin_user(username, password, display_name="系统管理员"):
    user = find_user_by_username(username)
    created = user is None
    if user is None:
        user = User(username=username)
        db.session.add(user)

    user.display_name = display_name
    user.password_hash = generate_password_hash(password)
    user.role = "admin"
    user.is_active = True
    db.session.commit()
    return user, created


def authenticate_user(payload: LoginPayload):
    user = find_user_by_username(payload.username)
    if user is None or not user.is_active or not check_password_hash(user.password_hash, payload.password):
        raise ApiError("账号或密码错误", 401, "AUTH_INVALID")

    user.last_login_at = datetime.now()
    db.session.commit()
    return user


def format_datetime(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=SHANGHAI_TIMEZONE)
    return value.isoformat(timespec="seconds")


def user_payload(user):
    return {
        "id": user.id,
        "username": user.username,
        "displayName": user.display_name,
        "role": user.role,
        "isActive": user.is_active,
        "createdAt": format_datetime(user.created_at),
        "lastLoginAt": format_datetime(user.last_login_at),
    }
