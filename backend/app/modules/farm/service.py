from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from ...core.errors import ApiError
from ...extensions import db
from ..auth.models import User
from ..auth.service import format_datetime, user_payload
from .models import Barn, Farm, FarmUser, Plot


def farm_payload(farm, member_count=0, access_role=None):
    return {
        "id": farm.id,
        "code": farm.code,
        "name": farm.name,
        "ownerName": farm.owner_name,
        "address": farm.address,
        "timezone": farm.timezone,
        "isActive": farm.is_active,
        "memberCount": member_count,
        "accessRole": access_role,
        "createdAt": format_datetime(farm.created_at),
        "updatedAt": format_datetime(farm.updated_at),
    }


def get_farm(farm_id):
    farm = db.session.get(Farm, farm_id)
    if farm is None:
        raise ApiError("农场不存在", 404, "FARM_NOT_FOUND")
    return farm


def get_accessible_farm(farm_id, actor):
    farm = get_farm(farm_id)
    if actor.role == "admin":
        return farm, "admin"

    membership = db.session.scalar(
        select(FarmUser).where(
            FarmUser.farm_id == farm.id,
            FarmUser.user_id == actor.id,
            FarmUser.is_active.is_(True),
        )
    )
    if membership is None or not farm.is_active:
        raise ApiError("无权访问该农场", 403, "FARM_ACCESS_DENIED")
    return farm, membership.role_code


def list_farms(query, actor):
    member_counts = (
        select(FarmUser.farm_id, func.count(FarmUser.id).label("member_count"))
        .where(FarmUser.is_active.is_(True))
        .group_by(FarmUser.farm_id)
        .subquery()
    )
    conditions = []
    if query.keyword:
        conditions.append(or_(
            Farm.code.contains(query.keyword, autoescape=True),
            Farm.name.contains(query.keyword, autoescape=True),
            Farm.owner_name.contains(query.keyword, autoescape=True),
        ))
    if query.status == "active":
        conditions.append(Farm.is_active.is_(True))
    elif query.status == "disabled":
        conditions.append(Farm.is_active.is_(False))

    if actor.role == "admin":
        statement = select(
            Farm,
            func.coalesce(member_counts.c.member_count, 0),
        ).outerjoin(member_counts, member_counts.c.farm_id == Farm.id)
        count_statement = select(func.count(Farm.id))
        access_role = "admin"
    else:
        conditions.extend((Farm.is_active.is_(True), FarmUser.is_active.is_(True), FarmUser.user_id == actor.id))
        statement = (
            select(Farm, func.coalesce(member_counts.c.member_count, 0), FarmUser.role_code)
            .join(FarmUser, FarmUser.farm_id == Farm.id)
            .outerjoin(member_counts, member_counts.c.farm_id == Farm.id)
        )
        count_statement = select(func.count(Farm.id)).join(FarmUser, FarmUser.farm_id == Farm.id)
        access_role = None

    total = db.session.scalar(count_statement.where(*conditions)) or 0
    rows = db.session.execute(
        statement
        .where(*conditions)
        .order_by(Farm.is_active.desc(), Farm.name.asc(), Farm.id.asc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    items = []
    for row in rows:
        role = access_role if actor.role == "admin" else row[2]
        items.append(farm_payload(row[0], row[1], role))
    return {
        "items": items,
        "pagination": {
            "page": query.page,
            "pageSize": query.page_size,
            "total": total,
            "totalPages": ceil(total / query.page_size) if total else 0,
        },
    }


def create_farm(payload, actor):
    farm = Farm(
        code=payload.code,
        name=payload.name,
        owner_name=payload.owner_name,
        address=payload.address,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.session.add(farm)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("农场编号已存在", 409, "FARM_CODE_EXISTS", "code") from error
    return farm_payload(farm, access_role="admin")


def update_farm(farm_id, payload, actor):
    farm = get_farm(farm_id)
    for field in ("code", "name", "owner_name", "address", "is_active"):
        if field in payload.model_fields_set:
            setattr(farm, field, getattr(payload, field))
    farm.updated_by_id = actor.id
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("农场编号已存在", 409, "FARM_CODE_EXISTS", "code") from error
    member_count = db.session.scalar(
        select(func.count(FarmUser.id)).where(FarmUser.farm_id == farm.id, FarmUser.is_active.is_(True))
    ) or 0
    return farm_payload(farm, member_count, "admin")


def member_payload(membership, user):
    return {
        "user": user_payload(user),
        "roleCode": membership.role_code,
        "isActive": membership.is_active,
        "createdAt": format_datetime(membership.created_at),
        "updatedAt": format_datetime(membership.updated_at),
    }


def list_farm_members(farm_id):
    get_farm(farm_id)
    rows = db.session.execute(
        select(FarmUser, User)
        .join(User, User.id == FarmUser.user_id)
        .where(FarmUser.farm_id == farm_id)
        .order_by(FarmUser.is_active.desc(), User.display_name.asc(), User.id.asc())
    ).all()
    return [member_payload(membership, user) for membership, user in rows]


def add_farm_member(farm_id, payload):
    get_farm(farm_id)
    user = db.session.get(User, payload.user_id)
    if user is None:
        raise ApiError("用户不存在", 404, "USER_NOT_FOUND")
    if not user.is_active:
        raise ApiError("不能分配已停用用户", 400, "USER_DISABLED")

    membership = db.session.scalar(
        select(FarmUser).where(FarmUser.farm_id == farm_id, FarmUser.user_id == user.id)
    )
    if membership is None:
        membership = FarmUser(farm_id=farm_id, user_id=user.id)
        db.session.add(membership)
    membership.role_code = payload.role_code
    membership.is_active = True
    db.session.commit()
    return member_payload(membership, user)


def update_farm_member(farm_id, user_id, payload):
    membership = db.session.scalar(
        select(FarmUser).where(FarmUser.farm_id == farm_id, FarmUser.user_id == user_id)
    )
    if membership is None:
        raise ApiError("农场成员不存在", 404, "FARM_MEMBER_NOT_FOUND")
    if payload.role_code is not None:
        membership.role_code = payload.role_code
    if payload.is_active is not None:
        membership.is_active = payload.is_active
    db.session.commit()
    user = db.session.get(User, user_id)
    return member_payload(membership, user)


def _paginated(items, query, total):
    return {
        "items": items,
        "pagination": {
            "page": query.page,
            "pageSize": query.page_size,
            "total": total,
            "totalPages": ceil(total / query.page_size) if total else 0,
        },
    }


def _resource_conditions(model, query, extra_search_fields=()):
    conditions = [model.farm_id == query.farm_id]
    if query.keyword:
        conditions.append(or_(
            model.code.contains(query.keyword, autoescape=True),
            model.name.contains(query.keyword, autoescape=True),
            *(field.contains(query.keyword, autoescape=True) for field in extra_search_fields),
        ))
    if query.status == "active":
        conditions.append(model.is_active.is_(True))
    elif query.status == "disabled":
        conditions.append(model.is_active.is_(False))
    return conditions


def _active_farm(farm_id):
    farm = get_farm(farm_id)
    if not farm.is_active:
        raise ApiError("农场已停用，不能新增基础资料", 409, "FARM_DISABLED")
    return farm


def barn_payload(barn):
    return {
        "id": barn.id,
        "farmId": barn.farm_id,
        "code": barn.code,
        "name": barn.name,
        "barnType": barn.barn_type,
        "capacity": barn.capacity,
        "isActive": barn.is_active,
        "createdAt": format_datetime(barn.created_at),
        "updatedAt": format_datetime(barn.updated_at),
    }


def list_barns(query, actor):
    get_accessible_farm(query.farm_id, actor)
    conditions = _resource_conditions(Barn, query)
    total = db.session.scalar(select(func.count(Barn.id)).where(*conditions)) or 0
    barns = db.session.execute(
        select(Barn)
        .where(*conditions)
        .order_by(Barn.is_active.desc(), Barn.name.asc(), Barn.id.asc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).scalars().all()
    return _paginated([barn_payload(barn) for barn in barns], query, total)


def create_barn(payload, actor):
    _active_farm(payload.farm_id)
    barn = Barn(
        farm_id=payload.farm_id,
        code=payload.code,
        name=payload.name,
        barn_type=payload.barn_type,
        capacity=payload.capacity,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.session.add(barn)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该农场内圈舍编号已存在", 409, "BARN_CODE_EXISTS", "code") from error
    return barn_payload(barn)


def update_barn(barn_id, payload, actor):
    barn = db.session.get(Barn, barn_id)
    if barn is None:
        raise ApiError("圈舍不存在", 404, "BARN_NOT_FOUND")
    for field in ("code", "name", "barn_type", "capacity", "is_active"):
        if field in payload.model_fields_set:
            setattr(barn, field, getattr(payload, field))
    barn.updated_by_id = actor.id
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该农场内圈舍编号已存在", 409, "BARN_CODE_EXISTS", "code") from error
    return barn_payload(barn)


def plot_payload(plot):
    area_mu = format(plot.area_mu, "f")
    if "." in area_mu:
        area_mu = area_mu.rstrip("0").rstrip(".")
    return {
        "id": plot.id,
        "farmId": plot.farm_id,
        "code": plot.code,
        "name": plot.name,
        "areaMu": area_mu,
        "soilType": plot.soil_type,
        "isActive": plot.is_active,
        "createdAt": format_datetime(plot.created_at),
        "updatedAt": format_datetime(plot.updated_at),
    }


def list_plots(query, actor):
    get_accessible_farm(query.farm_id, actor)
    conditions = _resource_conditions(Plot, query, (Plot.soil_type,))
    total = db.session.scalar(select(func.count(Plot.id)).where(*conditions)) or 0
    plots = db.session.execute(
        select(Plot)
        .where(*conditions)
        .order_by(Plot.is_active.desc(), Plot.name.asc(), Plot.id.asc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).scalars().all()
    return _paginated([plot_payload(plot) for plot in plots], query, total)


def create_plot(payload, actor):
    _active_farm(payload.farm_id)
    plot = Plot(
        farm_id=payload.farm_id,
        code=payload.code,
        name=payload.name,
        area_mu=payload.area_mu,
        soil_type=payload.soil_type,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.session.add(plot)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该农场内地块编号已存在", 409, "PLOT_CODE_EXISTS", "code") from error
    return plot_payload(plot)


def update_plot(plot_id, payload, actor):
    plot = db.session.get(Plot, plot_id)
    if plot is None:
        raise ApiError("地块不存在", 404, "PLOT_NOT_FOUND")
    for field in ("code", "name", "area_mu", "soil_type", "is_active"):
        if field in payload.model_fields_set:
            setattr(plot, field, getattr(payload, field))
    plot.updated_by_id = actor.id
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该农场内地块编号已存在", 409, "PLOT_CODE_EXISTS", "code") from error
    return plot_payload(plot)
