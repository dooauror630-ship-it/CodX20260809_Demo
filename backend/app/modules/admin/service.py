from math import ceil

from sqlalchemy import func, or_, select
from werkzeug.security import generate_password_hash

from ...core.errors import ApiError
from ...extensions import db
from ..auth.models import User
from ..auth.service import user_payload


def get_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError("用户不存在", 404, "USER_NOT_FOUND")
    return user


def list_users(query):
    conditions = []
    if query.keyword:
        conditions.append(or_(
            User.username.contains(query.keyword, autoescape=True),
            User.display_name.contains(query.keyword, autoescape=True),
        ))
    if query.role:
        conditions.append(User.role == query.role)
    if query.status == "active":
        conditions.append(User.is_active.is_(True))
    elif query.status == "disabled":
        conditions.append(User.is_active.is_(False))

    total = db.session.scalar(select(func.count(User.id)).where(*conditions)) or 0
    users = db.session.execute(
        select(User)
        .where(*conditions)
        .order_by(User.created_at.desc(), User.id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).scalars().all()
    return {
        "items": [user_payload(user) for user in users],
        "pagination": {
            "page": query.page,
            "pageSize": query.page_size,
            "total": total,
            "totalPages": ceil(total / query.page_size) if total else 0,
        },
    }


def update_user(user_id, payload, actor):
    user = get_user(user_id)
    if user.id == actor.id and payload.role not in (None, "admin"):
        raise ApiError("不能取消自己的管理员身份", 400, "ADMIN_SELF_PROTECTION")
    if user.id == actor.id and payload.is_active is False:
        raise ApiError("不能停用自己的管理员账号", 400, "ADMIN_SELF_PROTECTION")

    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.session.commit()
    return user


def reset_user_password(user_id, password):
    user = get_user(user_id)
    user.password_hash = generate_password_hash(password)
    db.session.commit()
    return user
